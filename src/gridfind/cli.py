"""The `gridfind` command: a working state in, a verdict out.

Reads either a combined `{puzzle, working_state}` document (the corpus
shape) from a file or stdin, or a SudokuMaker share link, sniffed and
decoded via `link_to_puzzle`. Either way it calls `verdict` and prints the
outcome: the verdict word, plus a rendered witness grid on `found`. All
logic lives in `main(argv, stdin) -> int` so tests drive it with an argv
and a stdin and read back stdout and the exit code;
`console_main` only wires `sys` for the `[project.scripts]` entry point.

Variants (doubler, Schrödinger) are inferred from the link's named marker
cages, so the CLI takes no variant flag.

Example:
    $ gridfind puzzle.json      # or:  gridfind < puzzle.json
    found
    1 4 7  2 3 9  5 6 8
    ...
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from gridfind.engine import GridfindError
from gridfind.puzzle import Puzzle, WorkingState
from gridfind.sudokumaker import link_to_puzzle
from gridfind.verdict import Verdict, verdict


def _is_link(value: str) -> bool:
    """A SudokuMaker share link, not a file path or a JSON document (a document
    starts with `{`, so the two never collide). Matches two shapes: the
    canonical host prefix, or an embedded `?puzzle=` payload."""
    value = value.strip()
    return (
        value.startswith("https://sudokumaker.app/")
        or "sudokumaker.app/?puzzle=" in value
    )


def main(argv: Sequence[str], stdin: TextIO) -> int:
    parser = argparse.ArgumentParser(
        prog="gridfind",
        description="Read a {puzzle, working_state} JSON document or a "
        "SudokuMaker link and print its verdict: found / broke / unknown.",
        epilog="examples:\n"
        "  gridfind puzzle.json               # a document from a file\n"
        "  gridfind < puzzle.json             # a document from stdin\n"
        "  gridfind 'https://sudokumaker.app/?puzzle=...'   # a share link\n"
        "  echo 'https://sudokumaker.app/?puzzle=...' | gridfind",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="a JSON document path or a SudokuMaker link; omit or use '-' "
        "to read stdin",
    )
    args = parser.parse_args(argv)

    try:
        if _is_link(args.file):
            text = args.file
        elif args.file == "-":
            text = stdin.read()
        else:
            text = Path(args.file).read_text()
    except OSError as err:
        print(f"gridfind: {err}", file=sys.stderr)
        return 2

    if not text.strip():
        parser.print_usage(sys.stderr)
        return 2

    try:
        result = _verdict_of(text)
    except (
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        GridfindError,
    ) as err:
        print(f"gridfind: invalid puzzle document: {err}", file=sys.stderr)
        return 2

    print(result.kind)
    if result.kind == "found" and result.witness is not None:
        print(result.witness.render())
    return 0 if result.kind == "found" else 1


def _verdict_of(text: str) -> Verdict:
    stripped = text.strip()
    if _is_link(stripped):
        puzzle, state = link_to_puzzle(stripped)
    else:
        doc = json.loads(stripped)
        puzzle = Puzzle.from_dict(doc["puzzle"])
        state = WorkingState.from_dict(doc["working_state"])
    return verdict(puzzle, state)


def console_main() -> None:
    """The `[project.scripts]` entry point: wires real `sys.argv`/`sys.stdin`
    into `main` and exits with its return code."""
    sys.exit(main(sys.argv[1:], sys.stdin))
