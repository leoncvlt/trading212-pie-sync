import os
import sys
import logging
import argparse
import json
import csv

from selenium.common.exceptions import InvalidArgumentException

from rich.logging import RichHandler
from rich.traceback import install as install_rich_tracebacks

from driver import ChromeDriver
from navigator import Navigator

install_rich_tracebacks()

log = logging.getLogger("trading-212-sync")


def main():
    # parse command line arguments
    argparser = argparse.ArgumentParser(
        description="Create and sync Trading212 pies holdings allocations to a shared pie or external source"
    )
    argparser.add_argument(
        "username", help="The email to log into your Trading212 account"
    )
    argparser.add_argument(
        "password", help="The password to log into your Trading212 account"
    )
    argparser.add_argument("pie", help="The name of the pie to update (case-sensitive)")

    argparser.add_argument(
        "--from-json",
        type=argparse.FileType("r"),
        help="Parse the list of holdings to update from a .json file "
        "with the format { [ticker]: [percentage], ... }",
    )
    argparser.add_argument(
        "--from-csv",
        type=argparse.FileType("r"),
        help="Parse the list of holdings to update from a .csv file "
        "with the format [ticker],[percentage] for each line",
    )
    argparser.add_argument(
        "--from-shared-pie",
        help="Parse the list of instruments to update from the URL of a shared pie",
    )
    argparser.add_argument(
        "-c",
        "--await-confirm",
        action="store_true",
        help="Do not commit changes automatically and wait for user to confirm",
    )
    argparser.add_argument(
        "-v", "--verbose", action="store_true", help="Increase output log verbosity"
    )
    args = argparser.parse_args()

    # configure logging for the application
    log.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    rich_handler = RichHandler()
    rich_handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
    log.addHandler(rich_handler)
    log.propagate = False

    # initialize chromedriver
    try:
        driver = ChromeDriver()
        n = Navigator(driver)
    except InvalidArgumentException as e:
        log.error(
            f"Error initalising ChromeDriver: {e}"
            + "Is another automated Chrome window still open?"
        )
        sys.exit(0)

    # start the application
    data = {"instruments": {}}
    if args.from_json:
        data = json.load(args.from_json)
    elif args.from_csv:
        reader = csv.reader(args.from_csv)
        data = {rows[0]: rows[1] for rows in reader}
    elif args.from_shared_pie:
        data = n.parse_shared_pie(args.from_shared_pie)

    n.open_dashboard(args.username, args.password)
    n.select_pie(args.pie)
    current_instruments = n.get_current_instruments_tickers()
    unused = [ticker for ticker in current_instruments if ticker not in data.keys()]
    for ticker in unused:
        n.remove_instrument(ticker)
    for ticker, distribution in data.items():
        n.rebalance_instrument(ticker, distribution)
    n.rebalance_pie()
    if not args.await_confirm:
        n.commit_pie_edits(name=args.pie)
    else:
        input("Confirm changes and then press Enter to close the browser...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.critical("Interrupted by user")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
