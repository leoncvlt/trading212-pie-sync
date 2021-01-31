from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

import chromedriver_autoinstaller

def get_chromedriver(headless=False):
    chromedriver_path = chromedriver_autoinstaller.install()
    logs_path = Path.cwd() / "logs" / "webdrive.log"
    logs_path.parent.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("window-size=1920,1080")
    chrome_options.add_argument("user-data-dir=" + str(Path.cwd() / "profile"));
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=4")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(
        executable_path=str(chromedriver_path),
        service_log_path=str(logs_path),
        options=chrome_options,
    )
    return driver