import json
import logging
from decimal import Decimal, getcontext
from math import copysign, remainder

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys

from driver import qS, qSS, wqS, qX, qXX, wait_for, wait_for_not, send_input

log = logging.getLogger(f"trading-212-sync.{__name__}")

# A custom selenium wait condition that waits until an instrument with a
# specific ticker appears in the instruments search bar and returns the
# [data-qa-code] attribute for that instrument's cell
class TickerFoundInInstrumentSearch(object):
    def __init__(self, search_field, ticker):
        self.search_field = search_field
        self.ticker = ticker

        self.search_field.send_keys(Keys.CONTROL + "a")
        self.search_field.send_keys(Keys.DELETE)
        self.search_field.send_keys(f"({ticker.upper()})")

    def __call__(self, driver):
        results = qSS(driver, ".search-results-content .search-results-instrument")
        if not len(results):
            return False
        for instrument in results:
            try:
                code = instrument.get_attribute("data-qa-code")
                cell = qS(driver, f".search-results-instrument[data-qa-code='{code}'")
                secondary_name = qS(cell, ".cell-name .secondary-name")
                if (
                    secondary_name.get_attribute("textContent")
                    == f"({self.ticker.upper()})"
                ):
                    return instrument.get_attribute("data-qa-code")
            except StaleElementReferenceException:
                pass
        return False


class Navigator:
    def __init__(self, driver):
        self.driver = driver

    def open_dashboard(self, username, password):
        self.driver.get("https://www.trading212.com/en/login")

        try:
            qS(self.driver, "#username-real").send_keys(username)
            qS(self.driver, "#pass-real").send_keys(password)
            qS(self.driver, "input[type=submit]").click()
        except:
            pass

        wait_for(self.driver, ".main-tabs")

        # wait until loader has disappeared completely as it can gets in the way of clicks
        wait_for_not(self.driver, "#platform-loader")
        try:
            # an account verification popup can sometimes appear for new accounts
            # if that's the case, just close it
            qS(self.driver, ".account-verification-popup .button").click()
            wait_for_not(self.driver, ".popup-overlay with-background")
        except:
            pass
        wait_for(self.driver, ".main-tabs")

    def parse_shared_pie(self, url):
        # navigate to the shared pie page and wait for it to load fully
        self.driver.get(url)
        WebDriverWait(self.driver, 10).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role=progressbar]"))
        )
        # parsing shared pie pages is a pain!
        # all the classes names are scrambled so we'll do all our parsing by XPaths
        # querying styling. This will likely require maintenance in the future
        instruments_xpath = "//div[contains(@style,'border-left-color') and contains(@style,'background-color: rgb(254, 254, 254)')]"
        instruments = qXX(self.driver, instruments_xpath)
        WebDriverWait(self.driver, 10).until(lambda d: len(instruments) > 0)

        container = qX(instruments[0], "./../..")
        # expands the instruments container height or else the driver will fail to
        # access them as they will be hidden by the overflow
        self.driver.execute_script("arguments[0].style='height: auto'", container)

        holdings = {}
        for instrument in instruments:
            ticker = qX(
                instrument,
                ".//div[contains(@style,'color: rgb(116, 121, 128)') and contains(@style, 'font-size: 12px;')]",
            ).text
            target = qX(instrument, ".//div[contains(text(), '%')]").text
            holdings[ticker] = float(target.strip("%"))
        return holdings

    def select_pie(self, pie_name):
        # click the portfolio section, wait for it to load and then open the pies tab
        wqS(self.driver, ".main-tabs div.portfolio-icon").click()
        wait_for(self.driver, ".portfolio-section .investments-section")
        wqS(self.driver, ".investments-section div[data-qa-tab=buckets]").click()
        try:
            # attempt to click the pie we want to modify
            wqS(
                self.driver,
                f".buckets-list .bucket-item[data-qa-item='{pie_name}']",
                timeout=5,
            ).click()
        except TimeoutException:
            # if the pie is not found, create a new one
            # and start adding new instruments to it
            log.error(f"Pie {pie_name} not found, creating new pie!")
            wqS(self.driver, f".buckets-list .bucket-creation-button").click()
            wqS(self.driver, f".bucket-creation .add-instruments .button").click()
            return

        # click the holdings tab on the pie section, then the edit pie button
        # and wait for the pie editing window to appear
        wqS(
            self.driver,
            ".bucket-advanced-tabs .bucket-advanced-tab[data-qa-tab=holdings]",
        ).click()
        wqS(self.driver, ".edit-bucket-button").click()
        wait_for(self.driver, ".bucket-customisation")

    # def get_pie_distribution(self):
    #     return float(
    #         qS(
    #             self.driver,
    #             ".bucket-customisation-footer .slices-distribution-indicator",
    #         )
    #         .get_attribute("textContent")
    #         .strip("%")
    #     )

    def redistribute_pie(self):
        # Trading212 now has a dedicated button for redistributing the pie
        # proportionally! So convennient.
        try:
            qS(self.driver, ".bucket-instruments-personalisation-header .adjust-slices-tooltip").click()
        except:
            log.debug("Pie does not need redistribution")

        return;
        # this code below is the old, lovingly handcrafted method.
        # couldn't bear myself to delete it!
        
        # get the total percentage of all instruments' target in the pie
        total_percentage = self.get_pie_distribution()
        total_redistributed = Decimal(0.0)
        rebalanced = False
        if total_percentage != 100.0:
            # if the total allocation percentage is less than 100, redistribute
            # the remaining value across all instruments
            log.info(f"Total pie percentage is {total_percentage}, redistributing to 100%")
            containers = ".bucket-customisation .bucket-instruments-personalisation .bucket-instrument-personalisation"
            for container in qSS(self.driver, containers):
                field = qS(container, ".instrument-share-container .spinner input")
                ticker = (
                    qS(container, ".instrument-logo-name")
                    .get_attribute("textContent")
                    .strip()
                )

                # go through each instrument container, and spread the remainder
                # proportionally according to its targets weight
                old_value = float(field.get_attribute("value"))
                new_value = round(old_value * 100.0 / total_percentage, 1)

                # if the total redistribution is going to exceed 100, clamp the value
                if (total_redistributed + Decimal(new_value)) > 100.0:
                    rebalanced = True
                    new_value = round((Decimal(100.0) - total_redistributed), 1)

                # set the new redistributed value for the target
                total_redistributed += Decimal(new_value)
                if new_value != old_value:
                    log.debug(f"Redistributing {ticker}: {old_value} → {new_value}")
                    send_input(field, new_value)

                if rebalanced:
                    break

            # if the pie distribution percentage still doesn't amount to 100%
            # after redistribution (likely due to floating point calculation errors)
            # spread the reminder across the top holdings (if positive), or subtract
            # it from the bottom ones (if negative) until we reach 100%
            distribution = self.get_pie_distribution()
            if distribution != 100.0:
                remainder = Decimal(100.0) - Decimal(distribution)
                log.debug(
                    f"Spreading out redistribution remainder ({round(remainder, 1)})"
                )
                fields = [
                    field
                    for field in qSS(
                        self.driver,
                        ".instrument-share-container .spinner input",
                    )
                ]
                fields.sort(
                    reverse=remainder > 0,
                    key=lambda field: Decimal(field.get_attribute("value")),
                )
                for field in fields:
                    value = float(field.get_attribute("value"))
                    # Trading212 allocation values can't go under 0.5
                    # so if we have a negative remainder and the current holding being
                    # shaved off has a 0.5 allocation, skip it for the next lowest one
                    if remainder < 0 and value == 0.5:
                        continue
                    offset = Decimal(copysign(0.1, remainder))
                    new_value = round(Decimal(value) + offset, 1)
                    send_input(field, new_value)
                    remainder = remainder - offset
                    if round(remainder, 1) == 0.0:
                        break

    def commit_pie_edits(self, name=""):
        try:
            # if a new pie is being created, fill the input field for the pie name
            name_input = qS(self.driver, ".bucket-creation .bucket-personalisation input")
            send_input(name_input, name)
            qS(self.driver, ".bucket-creation .button.complete-button").click()
            # then set up manual investing and complete the creation process
            wqS(
                self.driver, ".bucket-creation [data-qa-autoinvest-option='manual']"
            ).click()
            qS(self.driver, ".bucket-creation .button.complete-button").click()
        except NoSuchElementException:
            # if we are editing an existing pie, just confirm the changes
            qS(self.driver, ".bucket-customisation-footer .complete-button").click()

    def get_current_instruments_tickers(self):
        # returns a list of all the tickers of the instruments that are
        # currently included in the pies
        ticker_selector = ".bucket-instrument-personalisation .instrument-logo-name"
        return [
            element.get_attribute("textContent")
            for element in qSS(self.driver, ticker_selector)
        ]

    def rebalance_instrument(self, ticker, target, substitutions={}):
        # round up to one decimal digit since that's the max decimal numbers
        # theat the pie instrument spinner field support
        target = round(float(target), 1)
        if target < 0.5:
            # skip allocations smaller than 0.5 as that's the minimum weight
            # value supported by Trading212
            log.warning(f"Ticker {ticker}'s target weight is less than 0.5, skipping...")
            return

        try:
            # check if the instrument container with the specified ticker exists
            container = qX(
                self.driver,
                f"//div[@class='bucket-instrument-personalisation'"
                f"and .//div[text()='{ticker}']]",
            )
        except:
            # if not, add the instrument and attempt the re-balancing again
            # once the instrument has been added
            added_ticker = self.add_instrument(ticker, substitutions=substitutions)
            if added_ticker:
                self.rebalance_instrument(added_ticker, target)
            return

        # set the rebalanced value on the instrument's target input field
        field = qS(container, ".instrument-share-container .spinner input")
        previous_value = float(field.get_attribute("value"))
        if previous_value != target:
            log.info(f"Rebalacing {ticker}: {previous_value} → {target}")
            send_input(field, target)
            # the instrument value gets automatically locked as we do so,
            # click the unlock button to let the instrument be redistributed afterwards
            instrument_lock = qS(container, ".lock-unlock-tooltip")
            instrument_lock.click()

    def add_instrument(self, ticker, current_instruments_num=None, substitutions={}):
        # get the amount of current instruments
        if not current_instruments_num:
            current_instruments_num = len(self.get_current_instruments_tickers())

        try:
            # is the 'add slices to pie' popup already open? (happens on pie creation)
            qS(self.driver, ".bucket-creation .bucket-add-slices")
        except:
            # if not, click the 'add slice' button to open it
            qS(self.driver, ".button.add-slice-button").click()

        # wait for the search window to fully load
        search_field = wqS(self.driver, ".bucket-add-slices input.search-input")
        confirm_button = wqS(self.driver, ".bucket-add-slices-footer > .button")

        # if we reached the maximum amount of instruments in the pie,
        # we can't add more instruments - call it a day and go home
        if current_instruments_num == 50:
            log.error(
                f"Can't add {ticker} - maximum amount of instruments in pie reached"
            )
            confirm_button.click()
            return False

        try:
            # wait until the desired ticker is found in the search window, this will
            # return the Trading212 [data-qa-code] attrigute for that instrument
            instrument_code = WebDriverWait(self.driver, 2).until(
                TickerFoundInInstrumentSearch(search_field, ticker)
            )
        except TimeoutException:
            log.error(f"Instrument {ticker} not found!")
            if ticker in substitutions:
                # if the ticker was not found, see if we defined any replacement tickers
                # for it and re-attempt the adding process
                old_ticker = ticker
                ticker = substitutions[old_ticker]
                log.debug(f"Re-trying with ticker {old_ticker} substitution {ticker}")
                return self.add_instrument(ticker, current_instruments_num, substitutions)
            else:
                # if not, don't add any instruments and close the search window
                confirm_button.click()
                return False

        # select the instrument search result by using the [[data-qa-code] attribute
        # and add it to the list
        # TODO: Once in a blue moon this triggers a StaleElementException
        wqS(self.driver, f"[data-qa-code='{instrument_code}'] .add-to-bucket").click()
        confirm_button.click()

        log.info(f"Adding instrument {ticker}")

        # wait until the amount of current instruments reflects the addition
        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num + 1
        )
        return ticker

    def remove_instrument(self, ticker):
        # get the amount of current instruments
        current_instruments_num = len(self.get_current_instruments_tickers())

        # get the instrument container with the specified ticker to delete
        container = qX(
            self.driver,
            f"//div[@class='bucket-instrument-personalisation' and .//div[text()='{ticker}']]",
        )

        # click the delete button and confirm deletion on the popup
        qS(container, ".close-button").click()
        wait_for(self.driver, ".popup-content .dialog")
        log.info(f"Removing instrument {ticker}")
        qS(self.driver, ".popup-content .dialog .confirm-button").click()

        # wait until the amount of current instruments reflects the deletion
        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num - 1
        )

    def get_available_instruments(self):
        self.driver.get("https://www.trading212.com/en/Trade-Equities")
        wait_for(self.driver, "#all-equities")
        # cells = qSS(self.driver, "#all-equities [data-label='Instrument']")
        # instruments = [cell.get_attribute("textContent") for cell in cells]

        # using javascript is orders of magnitude faster than fetching the same
        # data with selenium
        instruments = self.driver.execute_script(
            "return Array.from(document.querySelectorAll(\"#all-equities [data-label='Instrument']\")).map(e => e.textContent)"
        )
        return instruments