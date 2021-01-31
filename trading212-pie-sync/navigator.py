import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, InvalidSessionIdException
from selenium.webdriver.common.keys import Keys

log = logging.getLogger(__name__)


class instruments_list_found_ticker(object):
    def __init__(self, instruments, ticker):
        self.instruments = instruments
        self.ticker = ticker

    def __call__(self, driver):
        if not len(self.instruments):
            return False
        for instrument in self.instruments:
            secondary_name = instrument.find_element_by_css_selector(
                ".cell-name .secondary-name"
            ).get_attribute("textContent")
            if secondary_name == f"({self.ticker.upper()})":
                return instrument
        return False


class Navigator:
    def __init__(self, driver):
        self.driver = driver

    def wait_for(self, selector, timeout=10):
        WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

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
        WebDriverWait(self.driver, 10).until_not(
            EC.presence_of_element_located((By.ID, "platform-loader"))
        )

        try:
            onboarding_button = ".account-verification-popup .button"
            self.driver.find_element_by_css_selector(onboarding_button).click()
            WebDriverWait(self.driver, 10).until_not(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".popup-overlay with-background")
                )
            )
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
            self.add_instrument(ticker)
            self.rebalance_instrument(ticker, target)
            return

        field = container.find_element_by_css_selector(
            ".instrument-share-container .spinner input"
        )
        field.send_keys(Keys.CONTROL + "a")
        field.send_keys(Keys.DELETE)
        field.send_keys(str(target))
        field.send_keys(Keys.RETURN)

    def get_current_instruments_tickers(self):
        ticker_selector = ".bucket-instrument-personalisation .instrument-logo-name"
        return [
            element.get_attribute("textContent")
            for element in self.driver.find_elements_by_css_selector(ticker_selector)
        ]

    def add_instrument(self, ticker):
        current_instruments_num = len(self.get_current_instruments_tickers())
        add_slice_button = ".button.add-slice-button"
        self.driver.find_element_by_css_selector(add_slice_button).click()

        instrument_search = ".bucket-edit .bucket-add-slices input.search-input"
        self.wait_for(instrument_search)
        field = self.driver.find_element_by_css_selector(instrument_search)
        field.send_keys(Keys.CONTROL + "a")
        field.send_keys(Keys.DELETE)
        field.send_keys(f"({ticker.upper()})")

        instruments = self.driver.find_elements_by_css_selector(
            ".search-results-instrument"
        )
        instrument = WebDriverWait(self.driver, 10).until(
            instruments_list_found_ticker(instruments, ticker)
        )
        # TODO: fix occasional staleness
        add_button = instrument.find_element_by_css_selector(".add-to-bucket")
        WebDriverWait(self.driver, 10).until_not(EC.staleness_of(add_button))
        add_button.click()
        confirm_button = ".bucket-add-slices-footer > .button"
        self.driver.find_element_by_css_selector(confirm_button).click()

        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num + 1
        )

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

        WebDriverWait(self.driver, 10).until(
            lambda d: len(self.get_current_instruments_tickers())
            == current_instruments_num - 1
        )

    def wait_for_browser_closed(self):
        while True:
            try:
                _ = self.driver.window_handles
            except InvalidSessionIdException as e:
                break
