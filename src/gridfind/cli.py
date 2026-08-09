"""The `gridfind` command: a working state in, a verdict out.

Milestone 1 (#56) reads one combined `{puzzle, working_state}` document (the
corpus shape) from a file or stdin; Milestone 2 (#60) also takes a SudokuMaker
share link, sniffed and decoded via `decode_link`. Either way it calls
`verdict` and prints the outcome: the verdict word, plus a rendered witness
grid on `found`. All logic lives in `main(argv, stdin) -> int` so tests drive
it with an argv and a stdin and read back stdout and the exit code;
`console_main` only wires `sys` for the `[project.scripts]` entry point.

`--schrodinger` and `--reading` (issue #143) declare a SudokuMaker link as a
Schrödinger puzzle and name its S-cell reading, threading straight through to
`decode_link`; they are meaningless for a `{puzzle, working_state}` document
and simply carried unused in that branch.

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
from gridfind.sudokumaker import decode_link
from gridfind.verdict import Verdict, verdict


def _is_link(value: str) -> bool:
    """A SudokuMaker share link, not a file path or a JSON document (a document
    starts with `{`, so the two never collide). Matches the two shapes #60
    enumerates: the canonical host prefix, or an embedded `?puzzle=` payload."""
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
    parser.add_argument(
        "--schrodinger",
        action="store_true",
        help="declare a SudokuMaker link as a Schrödinger puzzle (a red cell "
        "marks an S-cell); ignored for a {puzzle, working_state} document",
    )
    parser.add_argument(
        "--reading",
        default="classic",
        help="the Schrödinger S-cell reading to apply with --schrodinger "
        "(default: classic; only value built so far)",
    )
    args = parser.parse_args(argv)

    try:
        if _is_link(args.file):  # a link argument, not a file path to read
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
        result = _verdict_of(text, schrodinger=args.schrodinger, reading=args.reading)
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


def _verdict_of(
    text: str, *, schrodinger: bool = False, reading: str = "classic"
) -> Verdict:
    stripped = text.strip()
    if _is_link(stripped):
        puzzle, state = decode_link(stripped, schrodinger=schrodinger, reading=reading)
    else:
        doc = json.loads(stripped)
        puzzle = Puzzle.from_json(json.dumps(doc["puzzle"]))
        state = WorkingState.from_json(json.dumps(doc["working_state"]))
    return verdict(puzzle, state)


def console_main() -> None:
    sys.exit(main(sys.argv[1:], sys.stdin))
