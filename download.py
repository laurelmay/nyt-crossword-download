#!/usr/bin/env python3

import os
import subprocess
import sys
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from datetime import date

import click
import requests

from typing import TypedDict


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


def determine_date(puzzle_date: str | None) -> str:
    base = date.fromisoformat(puzzle_date) if puzzle_date else date.today()
    return base.isoformat()


def get_puzzle_id(session: requests.Session, desired_date: str | None) -> int:
    puzzle_date = determine_date(desired_date)
    params = {"date_start": puzzle_date, "date_end": puzzle_date}

    api_url = "https://www.nytimes.com/svc/crosswords/v3/76535102/puzzles.json"
    response: PuzzlesApiResponse = session.get(api_url, params=params).json()
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
    puzzle_url = f"https://www.nytimes.com/svc/crosswords/v2/puzzle/{puzzle_id}.pdf"
    soln_url = f"https://www.nytimes.com/svc/crosswords/v2/puzzle/{puzzle_id}.ans.pdf"
    params = {
        "southpaw": str(left_handed).lower(),
        "large_print": str(large_print).lower(),
    }
    puzzle_pdf = session.get(puzzle_url, params=params).content
    soln_pdf = session.get(soln_url).content
    return {
        "puzzle": puzzle_pdf,
        "solution": soln_pdf,
    }


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
    "do_print",
    default=False,
    show_default=True,
    help="Whether to send the PDFs to the default printer automatically",
)
def main(
    puzzle_date: str | None,
    large_print: bool,
    left_handed: bool,
    cookies: Path,
    out_dir: Path,
    do_print: bool
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
    with open(puzzle_filename, "wb") as puzzle_pdf:
        puzzle_pdf.write(files["puzzle"])
        print(f"Wrote {len(files['puzzle'])} bytes to {puzzle_filename}")
    with open(soln_filename, "wb") as soln_pdf:
        soln_pdf.write(files["solution"])
        print(f"Wrote {len(files['solution'])} bytes to {soln_filename}")

    if do_print:
        print(f"Sending {puzzle_filename} to default printer")
        try:
            result = subprocess.run(["lp", str(puzzle_filename)], capture_output=True)
            print(result.stdout)
        except subprocess.SubprocessError as e:
            print(str(e), file=sys.stderr)
        print(f"Sending {soln_filename} to default printer")
        try:
            result = subprocess.run(["lp", str(soln_filename)], capture_output=True)
            print(result.stdout)
        except subprocess.SubprocessError as e:
            print(str(e), file=sys.stderr)


if __name__ == "__main__":
    main()
