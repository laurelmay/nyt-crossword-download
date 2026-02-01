#!/usr/bin/env python3

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Never, TypedDict

import click
import requests

PUZZLES_API_URL = "https://www.nytimes.com/svc/crosswords/v3/puzzles.json"
PUZZLE_BASE_URL = "https://www.nytimes.com/svc/crosswords/v2/puzzle"
REQUIRED_COOKIES = ["NYT-S", "SIDNY"]

LOGGER = logging.getLogger(__name__)


class Puzzle(TypedDict):
    author: str
    editor: str
    format_type: str
    print_date: str
    publish_type: str
    puzzle_id: int
    title: str
    version: int
    percent_filled: int
    solved: bool
    star: str | None


class PuzzlesApiResponse(TypedDict):
    status: str
    results: list[Puzzle]


@dataclass
class DownloadedPuzzle:
    puzzle: bytes
    solution: bytes | None


class MissingCookieError(Exception):
    def __init__(self):
        super().__init__()


class InvalidDocumentError(Exception):
    def __init__(self, requested_type: str, url: str):
        self.requested_type = requested_type
        self.url = url

        super().__init__(f"The {requested_type} retrieved was not a valid PDF")


class FailedToListPuzzlesError(Exception):
    def __init__(self, date: str):
        self.date = date
        super().__init__(f"Listing puzzles for {date} failed")


class TooManyPuzzlesError(Exception):
    def __init__(self, date: str, count: int):
        self.date = date
        self.count = count
        super().__init__(
            f"Exactly 1 puzzle is expected but {count} were returned for {date}"
        )


def assert_required_cookie_present(jar: MozillaCookieJar) -> None | Never:
    for cookie in jar:
        if cookie.name in REQUIRED_COOKIES and cookie.domain.endswith("nytimes.com"):
            return
    raise MissingCookieError()


def looks_like_pdf(content: bytes) -> bool:
    return content.startswith(b"%PDF-")


def is_valid_pdf_response(response: requests.Response) -> bool:
    LOGGER.debug(
        "Checking if PDF: [status=%s,contentType=%s,initialBytes=%s",
        response.status_code,
        response.headers["Content-Type"],
        response.content[0:5],
    )
    return (
        response.ok
        and response.headers["Content-Type"].startswith("application/pdf")
        and looks_like_pdf(response.content)
    )


def determine_date(puzzle_date: str | None) -> str:
    base = date.fromisoformat(puzzle_date) if puzzle_date else date.today()
    return base.isoformat()


def get_puzzle_id(session: requests.Session, desired_date: str | None) -> int:
    puzzle_date = determine_date(desired_date)
    params = {
        "date_start": puzzle_date,
        "date_end": puzzle_date,
        "puzzle_type": "daily",
    }

    response = session.get(PUZZLES_API_URL, params=params)
    if response.status_code > 299:
        raise FailedToListPuzzlesError(puzzle_date)
    data: PuzzlesApiResponse = response.json()
    if data["status"] != "OK" or not data.get("results", None):
        raise FailedToListPuzzlesError(puzzle_date)
    puzzles = [
        puzzle for puzzle in data["results"] if puzzle["print_date"] == puzzle_date
    ]
    if len(puzzles) != 1:
        raise TooManyPuzzlesError(puzzle_date, len(puzzles))
    return puzzles[0]["puzzle_id"]


def download(
    session: requests.Session,
    puzzle_id: int,
    large_print: bool,
    left_handed: bool,
    ink_saver: bool,
    solution: bool,
) -> DownloadedPuzzle:
    puzzle_url = f"{PUZZLE_BASE_URL}/{puzzle_id}.pdf"
    soln_url = f"{PUZZLE_BASE_URL}/{puzzle_id}.ans.pdf"

    # Variations of the puzzle (left-handed or large-print) are retrieved via
    # URL query string parameters. These do not apply to the solution PDF.
    params = {
        # "southpaw" is the parameter name the API uses for left-handed puzzles
        "southpaw": str(left_handed).lower(),
        "large_print": str(large_print).lower(),
    }
    if ink_saver:
        # The request made by the NYT site always uses the value 30 for this
        # parameter, though it seems any value in the interval [1,100) is allowed.
        # Using 0 will result in the non-ink-saver variant and values greater than
        # 99 result in an error response. Regardless of the opacity value, the PDF
        # seems to actually have approximately the same opacity for the blocks
        params["block_opacity"] = "30"
    LOGGER.debug(
        "Requesting puzzle with parameters [url=%s,params=%s]", puzzle_url, params
    )
    puzzle_response = session.get(puzzle_url, params=params)
    if not is_valid_pdf_response(puzzle_response):
        raise InvalidDocumentError("puzzle", puzzle_url)
    puzzle_content = puzzle_response.content

    if solution:
        LOGGER.debug("Requesting solution with parameters [url=%s]", soln_url)
        solution_response = session.get(soln_url)
        if not is_valid_pdf_response(solution_response):
            raise InvalidDocumentError("solution", soln_url)
        solution_content = solution_response.content
    else:
        solution_content = None

    return DownloadedPuzzle(puzzle=puzzle_content, solution=solution_content)


def write_pdf(data: bytes, path: os.PathLike) -> None:
    LOGGER.debug("Writing to file [path=%s]: %s", path, data[:32])
    with open(path, "wb") as pdf:
        pdf.write(data)
    print(f"Wrote {len(data)} bytes to {path}")


def print_file(path: os.PathLike) -> None:
    LOGGER.debug("Printing for OS: %s", os.name)
    if os.name == "nt":
        try:
            LOGGER.debug("Attempting os.startfile with operation=print [path=%s]", path)
            # This function is only available on Windows
            os.startfile(path, "print")
        except OSError as e:
            if e.winerror == 1155:
                LOGGER.debug(
                    "Printing via os.startfile failed. Offering to open via default app without operation."
                )
                print(
                    "No application is registered to handle printing PDFs, make sure that an application is registered and that it supports printing",
                    file=sys.stderr,
                )
                print(
                    "This change can be made in Windows Settings. Note that you may have to end all tasks of the current default in Task Manager.",
                    file=sys.stderr,
                )
                if click.confirm(
                    "Would you like to try opening in the default app without automatically printing?"
                ):
                    try:
                        os.startfile(path)
                    except OSError as e:
                        print(
                            "The file failed to open in the default app.",
                            file=sys.stderr,
                        )
                        print(str(e), file=sys.stderr)
            else:
                print(str(e), file=sys.stderr)
            print()

    else:
        try:
            LOGGER.debug("Attempting to print via lp [path=%s]", path)
            result = subprocess.run(["lp", str(path)], capture_output=True)
            print(result.stdout)
        except subprocess.SubprocessError as e:
            print(str(e), file=sys.stderr)


@click.command("nyt-download")
@click.option(
    "--date",
    "-d",
    "puzzle_date",
    type=click.STRING,
    required=False,
    help="The date of the puzzle to fetch (defaults to today's puzzle)",
)
@click.option(
    "--large-print/--no-large-print",
    default=False,
    show_default=True,
    help="Whether to fetch the large-print puzzle variant",
)
@click.option(
    "--left-handed/--no-left-handed",
    default=False,
    show_default=True,
    help="Whether to fetch the left-handed puzzle variant",
)
@click.option(
    "--solution/--no-solution",
    default=True,
    show_default=True,
    help="Whether to also include the solution in the download/print",
)
@click.option(
    "--cookies",
    "-b",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default="./cookies.txt",
    show_default=True,
    help="The path to the Netscape-formatted cookies file with your NYT site cookies",
)
@click.option(
    "--out-dir",
    "-o",
    type=click.Path(exists=False, file_okay=False),
    default="out",
    show_default=True,
    help="The directory where the output PDFs should be placed",
)
@click.option(
    "--print/--no-print",
    "-p",
    "do_print",
    default=False,
    show_default=True,
    help="Whether to send the PDFs to the default printer automatically",
)
@click.option(
    "--ink-saver/--no-ink-saver",
    default=False,
    show_default=True,
    help="Whether to enable the 'Ink Saver' option, using less ink for black squares",
)
@click.option(
    "--verbose/--no-verbose",
    "-v",
    default=False,
    show_default=True,
    help="Enable verbose logging",
)
def main(
    puzzle_date: str | None,
    large_print: bool,
    left_handed: bool,
    ink_saver: bool,
    solution: bool,
    cookies: Path,
    out_dir: Path,
    do_print: bool,
    verbose: bool,
):
    logging.basicConfig(
        format="%(asctime)s:%(levelname)s: %(message)s",
        level=logging.DEBUG if verbose else logging.INFO,
    )

    LOGGER.debug("Loading Mozilla cookie jar from %s", cookies)
    jar = MozillaCookieJar(cookies)
    jar.load()
    LOGGER.debug(
        "Cookies loaded from jar [path=%s,cookies=%s]",
        cookies,
        [cookie.name for cookie in jar],
    )

    try:
        assert_required_cookie_present(jar)
    except MissingCookieError:
        print(
            "The required cookie for nytimes.com is not present in the provided cookies file.",
            file=sys.stderr,
        )
        print(
            "Please make sure that you've correctly followed the instructions for extracting cookies.",
            file=sys.stderr,
        )
        print(
            "If using Firefox, you can try to run the ./extract-cookies.sh script contained in this",
            file=sys.stderr,
        )
        print("directory.", file=sys.stderr)
        return

    session = requests.Session()
    session.cookies = jar  # type: ignore

    try:
        puzzle_id = get_puzzle_id(session, puzzle_date)
        LOGGER.debug("Puzzle ID %s", puzzle_id)
        files = download(
            session, puzzle_id, large_print, left_handed, ink_saver, solution
        )
    except TooManyPuzzlesError as e:
        print(
            "Typically when requesting puzzles for a date, only one puzzle will be returned;",
            file=sys.stderr,
        )
        print(
            f"however, in this case, {e.count} were returned for {e.date}. You can open an issue",
            file=sys.stderr,
        )
        print(
            "at https://github.com/laurelmay/nyt-puzzle/nyt-crossword-download/issues/new",
            file=sys.stderr,
        )
        print(
            "to report this. Please include the puzzle date that you requested.",
            file=sys.stderr,
        )
        return
    except FailedToListPuzzlesError as e:
        print(
            f"There was an error when trying to get the puzzle for {e.date}. This can be caused",
            file=sys.stderr,
        )
        print(
            "when the puzzle for the requested date is not yet available or if the requested",
            file=sys.stderr,
        )
        print(
            "date is prior to November 21, 1993. Further, this can occur if the provided cookies",
            file=sys.stderr,
        )
        print(
            "file has outdated or invalid cookies; please follow the steps to extract the",
            file=sys.stderr,
        )
        print("necessary cookies", file=sys.stderr)
        return
    except InvalidDocumentError:
        print(
            "A valid PDF was not returned when making a request for the puzzle. This can be",
            file=sys.stderr,
        )
        print(
            "caused by network connectivity problems. Please ensure you have a reliable connection",
            file=sys.stderr,
        )
        print(
            "and try again. If you continue to have errors, please also ensure that the provided",
            file=sys.stderr,
        )
        print(
            "cookies file has recent and valid cookies; follow the steps to extract the required",
            file=sys.stderr,
        )
        print("cookies.", file=sys.stderr)
        return

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    puzzle_filename = Path(out_dir, f"{determine_date(puzzle_date)}.pdf")
    soln_filename = Path(out_dir, f"{determine_date(puzzle_date)}.soln.pdf")
    write_pdf(files.puzzle, puzzle_filename)
    if solution and files.solution:
        write_pdf(files.solution, soln_filename)

    if do_print:
        print(f"Sending {puzzle_filename} to default printer")
        print_file(puzzle_filename)
        if solution:
            print(f"Sending {soln_filename} to default printer")
            print_file(soln_filename)


if __name__ == "__main__":
    main()
