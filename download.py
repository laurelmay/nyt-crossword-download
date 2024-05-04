#!/usr/bin/env python3

import os
import subprocess
import sys
from datetime import date
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import TypedDict

import click
import requests

PUZZLES_API_URL = "https://www.nytimes.com/svc/crosswords/v3/76535102/puzzles.json"
PUZZLE_BASE_URL = "https://www.nytimes.com/svc/crosswords/v2/puzzle"


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


class DownloadedPuzzle(TypedDict):
    puzzle: bytes
    solution: bytes


def looks_like_pdf(content: bytes) -> bool:
    return content.startswith(b"%PDF-")


def is_valid_pdf_response(response: requests.Response) -> bool:
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
    params = {"date_start": puzzle_date, "date_end": puzzle_date}

    response: PuzzlesApiResponse = session.get(PUZZLES_API_URL, params=params).json()
    if response["status"] != "OK" or not response.get("results", None):
        raise Exception(f"Unable to get puzzles for {puzzle_date}")
    puzzles = [
        puzzle for puzzle in response["results"] if puzzle["print_date"] == puzzle_date
    ]
    if len(puzzles) != 1:
        raise Exception(
            f"Expected exactly 1 puzzle for {puzzle_date} but found {len(puzzles)}"
        )
    return puzzles[0]["puzzle_id"]


def download(
    session: requests.Session, puzzle_id: int, large_print: bool, left_handed: bool
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
    puzzle_response = session.get(puzzle_url, params=params)
    solution_response = session.get(soln_url)

    if not is_valid_pdf_response(puzzle_response):
        raise Exception("Unable to retrieve a valid PDF for the puzzle")
    if not is_valid_pdf_response(solution_response):
        raise Exception("Unable to retrieve a valid PDF for the solution")

    return {
        "puzzle": puzzle_response.content,
        "solution": solution_response.content,
    }


def write_pdf(data: bytes, path: os.PathLike) -> None:
    with open(path, "wb") as pdf:
        pdf.write(data)
        print(f"Wrote {len(data)} bytes to {path}")


def print_file(path: os.PathLike) -> None:
    if os.name == "nt":
        try:
            # This function is only available on Windows
            os.startfile(path, "print")
        except OSError as e:
            if e.winerror == 1155:
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
def main(
    puzzle_date: str | None,
    large_print: bool,
    left_handed: bool,
    solution: bool,
    cookies: Path,
    out_dir: Path,
    do_print: bool,
):
    jar = MozillaCookieJar(cookies)
    jar.load()

    session = requests.Session()
    session.cookies = jar  # type: ignore

    puzzle_id = get_puzzle_id(session, puzzle_date)
    files = download(session, puzzle_id, large_print, left_handed)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    puzzle_filename = Path(out_dir, f"{determine_date(puzzle_date)}.pdf")
    soln_filename = Path(out_dir, f"{determine_date(puzzle_date)}.soln.pdf")
    write_pdf(files["puzzle"], puzzle_filename)
    if solution:
        write_pdf(files["solution"], soln_filename)

    if do_print:
        print(f"Sending {puzzle_filename} to default printer")
        print_file(puzzle_filename)
        if solution:
            print(f"Sending {soln_filename} to default printer")
            print_file(soln_filename)


if __name__ == "__main__":
    main()
