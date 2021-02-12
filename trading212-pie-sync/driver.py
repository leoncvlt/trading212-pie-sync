from pathlib import Path

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import chromedriver_autoinstaller

# higher-level abstraction methods to make selenium operations less verbose
def wait_for(driver, selector, timeout=10):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def wait_for_not(driver, selector, timeout=10):
    WebDriverWait(driver, timeout).until_not(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def qS(driver, selector):
    return driver.find_element_by_css_selector(selector)


def qSS(driver, selector):
    return driver.find_elements_by_css_selector(selector)


def wqS(driver, selector, timeout=10):
    wait_for(driver, selector, timeout)
    return driver.find_element_by_css_selector(selector)


def qX(driver, xpath):
    return driver.find_element_by_xpath(xpath)


def qXX(driver, xpath):
    return driver.find_elements_by_xpath(xpath)


def send_input(field, value):
    field.click()
    field.send_keys(Keys.CONTROL + "a")
    field.send_keys(Keys.DELETE)
    field.click()
    field.send_keys(str(value))
    field.click()
    field.send_keys("\t")


class ChromeDriver(Chrome):
    def __init__(self, *args, headless=False, **kwargs):
        chromedriver_path = chromedriver_autoinstaller.install()
        logs_path = Path.cwd() / "logs" / "webdrive.log"
        logs_path.parent.mkdir(parents=True, exist_ok=True)

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("window-size=1920,1080")
        chrome_options.add_argument("user-data-dir=" + str(Path.cwd() / "profile"))
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--log-level=4")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

        super().__init__(
            executable_path=str(chromedriver_path),
            service_log_path=str(logs_path),
            options=chrome_options,
        )