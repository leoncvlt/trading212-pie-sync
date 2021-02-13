# trading212-pie-sync

A python tool to automatically create / update Trading212 pies and sync their holdings' allocations to another shared pie or external source

## Installation & Requirements

Make sure you're in your virtual environment of choice, then run
- `poetry install --no-dev` if you have [Poetry](https://python-poetry.org/) installed
- `pip install -r requirements.txt` otherwise

## Usage
```
trading212-pie-sync [-h] [--from-json FROM_JSON] [--from-csv FROM_CSV] [--from-shared-pie FROM_SHARED_PIE] [-c] [-v] username password pie

positional arguments:
  username              The email to log into your Trading212 account
  password              The password to log into your Trading212 account
  pie                   The name of the pie to update (case-sensitive)

optional arguments:
  -h, --help            show this help message and exit
  --from-json FROM_JSON
                        Parse the list of holdings to update from this .json file with the format { [ticker]: [percentage], ... }
  --from-csv FROM_CSV   Parse the list of holdings to update from this .csv file with the format [ticker],[percentage] for each line
  --from-shared-pie FROM_SHARED_PIE
                        Parse the list of instruments to update from the URL of a shared pie
  --substitutions SUBSTITUTIONS
                        Parse a list of replacement tickers from this .json file, To be used when a ticker is not found. The list format is { [original ticker]: [ticker to use if original not found], ... }
  -c, --await-confirm   Do not commit changes automatically and wait for user to confirm
  -v, --verbose         Increase output log verbosity
```

## Explanation
[Trading212](trading212.com) pies are great! But editing allocations can be time consuming for pies with a lot of holdings, especially if you prefer a "set-and-forget" investement strategy. Moreover, while the social aspect of pie sharing is encouraged, once you copy someone's else pie it won't automatically update when the original changes, making the copy of actively-managed pies a bit pointless.

This script attempts to solve both problems by automating the process of updating a pie's holdings from another shared pie, or an external file.

Since Trading212 lacks an API (which is apparently in the works), this tool uses an automated Chromedriver window to perform all operations on your pies.

To start, supply the tool with your Trading212's email, password and the target pie name (case-sensitive, will be created if it doesn't exists):
`python trading212-pie-sync myname@email.com meg@mypassword "My Pie"`

Then, supply a data source to fetch the holdings information from:
- `--from-shared-pie https://www.trading212.com/pies/thesharedpieurl`: mirrors a shared pie's holdings allocation. Make sure the pie is public and the URL exists.
- `--from-csv my_csv_file.csv`: reads the holdings allocation from a .csv file. The format is `[ticker],[percentage]` for each line. My other tool [etf4u](https://github.com/leoncvlt/etf4u) scrapes and exports ETF funds allocations data in this format.
- `--from-json my_json_file.file`: reads the holdings allocation from a .json file. The format is `{ [ticker]: [percentage], ... }` for each line.

Finally, pass the `--c` flag if you don't trust the script and want to review all changes before commiting the pie edits.

### Instruments substitutions
Not all stocks might be available on Trading212 - if one of the sources you are syncing changes with contains a stock that you is not present on the platform, you can set a up a substitution for it by editing the `substitutions.json` file and adding an entry with the format `[original ticker]: [ticker to use if original not found]`. Alternatively, you can use your own substitutions json file with the flag `--substitutions`.

## Known Bugs
- Keep the automated window on the front / don't minimized it while it's running, or else it might jam the process.
- Once in a blue moon, you might get a `StaleElementException` - simply restart the script in that case.
- If the process appears to stop at some point / clicking / opening the wrong things, try deleting the `profile` folder (which contains cookies and settings for the automated browser session)