import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.keys import Keys

import math

log = logging.getLogger(__name__)


# class InstrumentNotFoundException(Exception):
# pass


# class ResultsNumberChanged(object):
#     def __init__(self, old_number):
#         self.old_number = old_number

#     def __call__(self, driver):
#         new_number = len(
#             driver.find_elements_by_css_selector(
#                 ".search-results-content .search-results-instrument"
#             )
#         )
#         return new_number != self.old_number


# class instruments_list_found_ticker(object):
#     def __init__(self, search_field, ticker):
#         self.search_field = search_field
#         self.ticker = ticker

#     def get_results(self, driver):
#         return driver.find_elements_by_css_selector(
#             ".search-results-content .search-results-instrument"
#         )

#     def clear(self):
#         self.search_field.send_keys(Keys.CONTROL + "a")
#         self.search_field.send_keys(Keys.DELETE)

#     def search(self, term):
#         self.clear()
#         self.search_field.send_keys(term)

#     def close(self, driver):
#         self.clear()
#         WebDriverWait(driver, 10).until(ResultsNumberChanged(self.last_results_count))

#     def __call__(self, driver):
#         if not hasattr(self, "last_results_count"):
#             self.last_results_count = len(self.get_results(driver))
#         self.search(f"({self.ticker.upper()})")
#         WebDriverWait(driver, 10).until(ResultsNumberChanged(self.last_results_count))
#         new_results = self.get_results(driver)
#         self.last_results_count = len(new_results)
#         if "no-results" in driver.find_element_by_css_selector(
#             ".search-results-content"
#         ).get_attribute("class"):
#             self.close(driver)
#             raise InstrumentNotFoundException()
#         for instrument in new_results:
#             secondary_name = instrument.find_element_by_css_selector(
#                 ".cell-name .secondary-name"
#             ).get_attribute("textContent")
#             if secondary_name == f"({self.ticker.upper()})":
#                 self.close(driver)
#                 return instrument
#         return False


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
            secondary_name = instrument.find_element_by_css_selector(
                ".cell-name .secondary-name"
            ).get_attribute("textContent")
            if secondary_name == f"({self.ticker.upper()})":
                return instrument
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

    def wqS(self, selector):
        self.wait_for(selector)
        return self.driver.find_element_by_css_selector(selector)

    def qX(self, xpath):
        return self.driver.find_elements_by_xpath(xpath)

    def send_input(self, field, value):
        field.send_keys(Keys.CONTROL + "a")
        field.send_keys(Keys.DELETE)
        field.send_keys(str(value))
        field.send_keys("\t")

    def open_dashboard(self, username, password):
        self.driver.get("https://live.trading212.com/beta")

        try:
            self.driver.find_element_by_id("username-real").send_keys(username)
            self.driver.find_element_by_id("pass-real").send_keys(password)
            self.driver.find_element_by_css_selector("input[type=submit]").click()
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
        portfolio_button_selector = ".main-tabs div.portfolio-icon"
        self.driver.find_element_by_css_selector(portfolio_button_selector).click()

        investment_section = ".portfolio-section .investments-section"
        self.wait_for(investment_section)

        pies_section = ".investments-section div[data-qa-tab=buckets]"
        self.wait_for(pies_section)
        self.driver.find_element_by_css_selector(pies_section).click()

        pie_selector = f".buckets-list .bucket-item[data-qa-item={pie_name}]"
        self.wait_for(pie_selector)
        self.driver.find_element_by_css_selector(pie_selector).click()

        holdings_tab = ".bucket-advanced-tabs .bucket-advanced-tab[data-qa-tab=holdings]"
        self.wait_for(holdings_tab)
        self.driver.find_element_by_css_selector(holdings_tab).click()

        edit_pie_button = ".edit-bucket-button"
        self.wait_for(edit_pie_button)
        self.driver.find_element_by_css_selector(edit_pie_button).click()
        self.wait_for(".bucket-customisation")

    def rebalance_instrument(self, ticker, target):
        try:
            container = self.driver.find_element_by_xpath(
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
        field.send_keys(Keys.CONTROL + "a")
        field.send_keys(Keys.DELETE)
        field.send_keys(str(target))
        field.send_keys(Keys.RETURN)

    def redistribute_pie(self):
        total_percentage = sum(
            [
                float(field.get_attribute("value"))
                for field in self.qSS(".instrument-share-container .spinner input")
            ]
        )
        offset = 0;
        if (total_percentage != 100.0):
            print(total_percentage)
            for field in self.qSS(".instrument-share-container .spinner input"):
                old_value = float(field.get_attribute("value"))
                new_value = round(old_value * 100.0 / total_percentage, 1)
                print(f"{old_value} > {new_value}")
                offset += new_value;
                self.send_input(field, new_value);

            top_holding_field = self.qSS(".instrument-share-container .spinner input")[0]
            top_value = float(top_holding_field.get_attribute("value"))
            new_top_value = round(top_value + (100.0 - offset), 1)
            self.send_input(top_holding_field, new_top_value)

    def get_current_instruments_tickers(self):
        ticker_selector = ".bucket-instrument-personalisation .instrument-logo-name"
        return [
            element.get_attribute("textContent") for element in self.qSS(ticker_selector)
        ]

    def add_instrument(self, ticker):
        # get the amount of current instruments
        current_instruments_num = len(self.get_current_instruments_tickers())
        self.qS(".button.add-slice-button").click()

        search_field = self.wqS(".bucket-edit .bucket-add-slices input.search-input")
        confirm_button = self.wqS(".bucket-add-slices-footer > .button")
        try:
            instrument = WebDriverWait(self.driver, 5).until(
                TickerFoundInInstrumentSearch(search_field, ticker)
            )
        except TimeoutException:
            log.error(f"Instrument with ticker {ticker} not found!")
            confirm_button.click()
            return False

        self.qS(".add-to-bucket").click()
        confirm_button.click()

        # wait until the amount of current instruments reflects the addition
        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num + 1
        )
        return True

    def remove_instrument(self, ticker):
        current_instruments_num = len(self.get_current_instruments_tickers())
        container = self.driver.find_element_by_xpath(
            f"//div[@class='bucket-instrument-personalisation' and .//div[text()='{ticker}']]"
        )
        delete_button = container.find_element_by_css_selector(".close-button")
        delete_button.click()
        self.wait_for(".popup-content .dialog")
        confirm_button = self.driver.find_element_by_css_selector(
            ".popup-content .dialog .confirm-button"
        )
        confirm_button.click()

        # wait until the amount of current instruments reflects the deletion
        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num - 1
        )

    # def wait_for_browser_closed(self):
    #     while True:
    #         try:
    #             _ = self.driver.window_handles
    #         except InvalidSessionIdException as e:
    #             break
