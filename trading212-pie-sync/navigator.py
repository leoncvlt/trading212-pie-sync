import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.keys import Keys

log = logging.getLogger(f"trading-212-sync.{__name__}")


class TickerFoundInInstrumentSearch(object):
    def __init__(self, search_field, ticker):
        self.search_field = search_field
        self.ticker = ticker

        self.search_field.send_keys(Keys.CONTROL + "a")
        self.search_field.send_keys(Keys.DELETE)
        self.search_field.send_keys(f"({ticker.upper()})")

    def __call__(self, driver):
        results = driver.find_elements_by_css_selector(
            ".search-results-content .search-results-instrument"
        )
        if not len(results):
            return False
        for instrument in results:
            try:
                code = instrument.get_attribute("data-qa-code")
                cell = driver.find_element_by_css_selector(
                    f".search-results-instrument[data-qa-code='{code}'"
                )
                secondary_name = cell.find_element_by_css_selector(
                    ".cell-name .secondary-name"
                )
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

    # Bunch of higher-level helper methods to make selenium less verbose
    def wait_for(self, selector, timeout=10):
        WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def wait_for_not(self, selector, timeout=10):
        WebDriverWait(self.driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def qS(self, selector):
        return self.driver.find_element_by_css_selector(selector)

    def qSS(self, selector):
        return self.driver.find_elements_by_css_selector(selector)

    def wqS(self, selector, timeout=10):
        self.wait_for(selector, timeout)
        return self.driver.find_element_by_css_selector(selector)

    def qX(self, xpath):
        return self.driver.find_element_by_xpath(xpath)

    def send_input(self, field, value):
        field.click()
        field.send_keys(Keys.CONTROL + "a")
        field.send_keys(Keys.DELETE)
        field.click()
        field.send_keys(str(value))
        field.click()
        field.send_keys("\t")

    def open_dashboard(self, username, password):
        self.driver.get("https://live.trading212.com/beta")

        try:
            self.qS("#username-real").send_keys(username)
            self.qS("#pass-real").send_keys(password)
            self.qS("input[type=submit]").click()
        except:
            pass

        self.wait_for(".main-tabs")

        # wait until loader has disappeared completely as it can gets in the way of clicks
        self.wait_for_not("#platform-loader")
        try:
            self.qS(".account-verification-popup .button").click()
            self.wait_for_not(".popup-overlay with-background")
        except:
            pass

    def parse_shared_pie(self, url):
        self.driver.get(url)
        WebDriverWait(self.driver, 10).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role=progressbar]"))
        )
        instruments_xpath = "//div[contains(@style,'border-left-color') and contains(@style,'background-color: rgb(254, 254, 254)')]"
        instruments = self.driver.find_elements_by_xpath(instruments_xpath)
        # TODO: wait until instruments > 0

        container = instruments[0].find_element_by_xpath("./../..")
        self.driver.execute_script("arguments[0].style='height: auto'", container)
        data = {}
        for instrument in instruments:
            ticker = instrument.find_element_by_xpath(
                ".//div[contains(@style,'color: rgb(116, 121, 128)') and contains(@style, 'font-size: 12px;')]"
            ).text
            distribution = instrument.find_element_by_xpath(
                ".//div[contains(text(), '%')]"
            ).text
            data[ticker] = float(distribution.strip("%"))
        return {"instruments": data}

    def select_pie(self, pie_name):
        self.qS(".main-tabs div.portfolio-icon").click()
        self.wait_for(".portfolio-section .investments-section")
        self.wqS(".investments-section div[data-qa-tab=buckets]").click()
        try:
            self.wqS(
                f".buckets-list .bucket-item[data-qa-item='{pie_name}']", timeout=5
            ).click()
        except TimeoutException:
            log.error(f"Pie {pie_name} not found!")
            return False
        self.wqS(
            ".bucket-advanced-tabs .bucket-advanced-tab[data-qa-tab=holdings]"
        ).click()
        self.wqS(".edit-bucket-button").click()
        self.wait_for(".bucket-customisation")
        return True

    def create_new_pie(self):
        self.wqS(f".buckets-list .bucket-creation-button").click()
        self.wqS(f".bucket-creation .add-instruments .button").click()

    def rebalance_instrument(self, ticker, target):
        try:
            container = self.qX(
                f"//div[@class='bucket-instrument-personalisation' and .//div[text()='{ticker}']]"
            )
        except:
            new_instrument_added = self.add_instrument(ticker)
            if new_instrument_added:
                self.rebalance_instrument(ticker, target)
            return

        field = container.find_element_by_css_selector(
            ".instrument-share-container .spinner input"
        )
        if float(field.get_attribute("value") != target):
            log.info(f"Rebalacing {ticker} to {target}%")
            self.send_input(field, str(target))

    def redistribute_pie(self):
        total_percentage = sum(
            [
                float(field.get_attribute("value"))
                for field in self.qSS(".instrument-share-container .spinner input")
            ]
        )
        total_percentage = round(total_percentage, 2)
        offset = 0
        if total_percentage != 100.0:
            log.info(f"Total percentage is {total_percentage}, rebalancing pie...")
            for field in self.qSS(".instrument-share-container .spinner input"):
                old_value = float(field.get_attribute("value"))
                new_value = round(old_value * 100.0 / total_percentage, 1)
                offset += new_value
                log.debug(f"{old_value} →  {new_value}")
                self.send_input(field, new_value)

            top_holding_field = max(
                [
                    holding
                    for holding in self.qSS(".instrument-share-container .spinner input")
                ],
                key=lambda field: float(field.get_attribute("value")),
            )
            top_value = float(top_holding_field.get_attribute("value"))
            new_top_value = round(top_value + (100.0 - offset), 1)
            log.debug(f"{top_value} →  {new_top_value}")
            self.send_input(top_holding_field, new_top_value)

    def commit_pie_edits(self, name=""):
        try:
            name_input = self.qS(".bucket-creation .bucket-personalisation input")
            self.send_input(name_input, name)
        except Exception:
            pass
        self.qS(".bucket-customisation-footer .complete-button").click()

    def get_current_instruments_tickers(self):
        ticker_selector = ".bucket-instrument-personalisation .instrument-logo-name"
        return [
            element.get_attribute("textContent") for element in self.qSS(ticker_selector)
        ]

    def add_instrument(self, ticker):
        # get the amount of current instruments
        current_instruments_num = len(self.get_current_instruments_tickers())

        try:
            # if the 'add slices to pie' popup already open? (happens on pie creation)
            self.qS(".bucket-creation .bucket-add-slices")
        except:
            # if not, click the 'add slice' button to open it
            self.qS(".button.add-slice-button").click()

        search_field = self.wqS(".bucket-add-slices input.search-input")
        confirm_button = self.wqS(".bucket-add-slices-footer > .button")

        if current_instruments_num == 50:
            log.error(
                f"Can't add {ticker} - maximum amount of instruments in pie reached"
            )
            confirm_button.click()
            return False

        try:
            instrument_code = WebDriverWait(self.driver, 2).until(
                TickerFoundInInstrumentSearch(search_field, ticker)
            )
        except TimeoutException:
            log.error(f"Instrument {ticker} not found!")
            confirm_button.click()
            return False

        self.wqS(f"[data-qa-code='{instrument_code}'] .add-to-bucket").click()
        confirm_button.click()

        log.info(f"Adding instrument {ticker}")

        # wait until the amount of current instruments reflects the addition
        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num + 1
        )
        return True

    def remove_instrument(self, ticker):
        current_instruments_num = len(self.get_current_instruments_tickers())
        container = self.qX(
            f"//div[@class='bucket-instrument-personalisation' and .//div[text()='{ticker}']]"
        )
        container.find_element_by_css_selector(".close-button").click()
        self.wait_for(".popup-content .dialog")
        log.info(f"Removing instrument {ticker}")
        self.qS(".popup-content .dialog .confirm-button").click()

        # wait until the amount of current instruments reflects the deletion
        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num - 1
        )