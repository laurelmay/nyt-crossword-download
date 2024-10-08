# NYT Crossword Downloader

This tool supports downloading (and automatically printing) the NYT crossword
puzzle. Using this script requires a valid login session for the NYT site. You
will need to provide your cookies for `nytimes.com` in the
[Netscape format][cookie-format] (that is also used by curl). This does not
support bypassing any subscription requirements to access crosswords.

## Prerequisites

- Python
- File with cookies (see: [HTTP Cookies][cookie-format]) for `nytimes.com`

### Extracting cookies

The necessary cookies are the `NYT-S` and/or the `SIDNY` cookies from the NYT
site. These can be found using browser dev tools and written to a file in the
[appropriate format][cookie-format]. There may also be browser extensions that
can export the cookies.

For Firefox users on Linux, the included `extract-cookies.sh` script can be run
to extract the cookies from the Firefox cookies database. This requires Firefox
to be closed; additionally replace `aaaaaaaa.default-release` in the following
command with the path to your profile in `~/.mozilla/firefox`. The script requires
the `sqlite3` command to be installed.

```bash
./extract-cookies.sh ~/.mozilla/firefox/aaaaaaaa.default-release/cookies.sqlite > cookies.txt
```

If you are unable to find the required cookies or if the cookies do not work
after extracting them, make sure you are correctly signed in to the NYT website.

## Running

To run the script, first install the dependencies from `requirements.txt`. This
is probably best done in a virtual environment.
Use `pip install -r requirements.txt`.

You can then run the script as `./download.py`. Several command line flags are supported:

- `--date`, `-d` - The date (`YYYY-MM-DD`) of the puzzle (defaults to today's date,
  notably **not** the latest puzzle)
- `--large-print` - Fetch the large-print variant of the puzzle
- `--left-handed` - Fetch the left-handed variant of the puzzle
- `--solution` - Fetch the solution in addition to the puzzle (default to enabled)
- `--print`, `-p` - Automatically send the puzzle (and solution if chosen) PDF
  to the printer using [`lp(1)`][lp-man]
- `--out-dir`, `-o` - The directory where PDFs should be written
- `--cookies`, `-b` - The path to the cookie file (defaults to `./cookies.txt`)

So for example, to automatically print the left-handed variant of the July 14, 2022
puzzle and download to `puzzles/`:

```bash
./download.py -p -d 2022-07-24 --left-handed -o puzzles
```

### Printing on Windows

On Windows, the default application for PDFs must support automatically printing.
You can check if the registered default application supports this by checking
if right-clicking on a PDF in Windows Explorer shows a "Print" option (you may
need to select "Show more options"). If not, you will need to change your default
application in the Settings app. You may need to end all tasks for the currently
registered default in order to change it.  If your current default is
Microsoft Edge (which does not support printing), you may have to end the
relevant Edge or `msedge` tasks from within Task Manager before changing the
default app.

Another downside with printing on Windows is that the default PDF app may remain
open after printing is done. Python does not provide any information about the
launched process from its `os.startfile` function so, unfortunately, there isn't
much to do about that.

[cookie-format]: https://curl.se/docs/http-cookies.html
[lp-man]: https://man.archlinux.org/man/lp.1.en
