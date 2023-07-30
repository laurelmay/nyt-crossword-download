# NYT Crossword Downloader

This tool supports downloading (and automatically printing) the NYT crossword puzzle. Using
this script requires a valid login session for the NYT site. You will need to provide your
cookies for `nytimes.com` in the [Netscape format][cookie-format] (that is also used by curl).
This does not support bypassing any subscription requirements to access crosswords.

## Prerequisites

- Python
- File with cookies (see: [HTTP Cookies][cookie-format]) for `nytimes.com`

## Running

To run the script, first install the dependencies from `requirements.txt`. This is probably best
done in a virtual environment. Use `pip install -r requirements.txt`.

You can then run the script as `./download.py`. Several command line flags are supported:

- `--date`, `-d` - The date (`YYYY-MM-DD`) of the puzzle (defaults to today's date, notably **not** the latest puzzle)
- `--large-print` - Fetch the large-print variant of the puzzle
- `--left-handed` - Fetch the left-handed variant of the puzzle
- `--print`, `-p` - Automatically send the puzzle (and solution) PDF to the printer using [`lp(1)`][lp-man]
- `--out-dir`, `-o` - The directory where PDFs should be written
- `--cookies`, `-b` - The path to the cookie file (defaults to `./cookies.txt`)

So for example, to automically print the left-handed variant of the July 14, 2022 puzzle and download to `puzzles/`:

```bash
./download.py -p -d 2022-07-24 --left-handed -o puzzles
```

[cookie-format]: https://curl.se/docs/http-cookies.html
[lp-man]: https://man.archlinux.org/man/lp.1.en
