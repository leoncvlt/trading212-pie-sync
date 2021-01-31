__version__ = "0.1.0"

import os
import sys
import logging
import argparse
import random
import json

log = logging.getLogger()

from rich.logging import RichHandler
from rich.traceback import install as install_rich_tracebacks

from driver import get_chromedriver
from navigator import Navigator

install_rich_tracebacks()


def main():
    # parse command line arguments
    argparser = argparse.ArgumentParser(
        description="Syncs Trading212 pies allocation to a shared pie or external source"
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
        help="Parse the list of instruments to update from a .json file "
        "with the format {'instruments': { [ticker]: [percentage], ... }}",
    )
    argparser.add_argument(
        "--from-shared-pie",
        help="Parse the list of instruments to update from the URL of a shared pie",
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

    # start the application
    n = Navigator(get_chromedriver())
    data = {"instruments": {}}
    if args.from_json:
        data = json.load(args.from_json)
    elif args.from_shared_pie:
        data = n.parse_shared_pie(args.from_shared_pie)

    n.open_dashboard(args.username, args.password)
    n.select_pie(args.pie)
    current_instruments = n.get_current_instruments_tickers()
    # for ticker, distrubution in data["instruments"].items():
    #     n.rebalance_instrument(ticker, distrubution)
    for ticker in current_instruments:
        n.remove_instrument(ticker)
    # n.wait_for_browser_closed()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.critical("Interrupted by user")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
