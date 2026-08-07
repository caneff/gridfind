"""The `gridfind` command: a working-state JSON document in, a verdict out.

Milestone 1 (#56) — the first user-facing entry point. Reads one combined
`{puzzle, working_state}` document (the corpus shape) from a file or stdin,
calls `verdict`, and prints the outcome: the verdict word, plus a rendered
witness grid on `found`. All logic lives in `main(argv, stdin) -> int` so tests
drive it with an argv and a stdin and read back stdout and the exit code;
`console_main` only wires `sys` for the `[project.scripts]` entry point.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from gridfind.puzzle import Puzzle, WorkingState
from gridfind.verdict import Verdict, verdict


def main(argv: Sequence[str], stdin: TextIO) -> int:
    parser = argparse.ArgumentParser(
        prog="gridfind",
        description="Read a {puzzle, working_state} JSON document and print its "
        "verdict: found / broke / unknown.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="path to the JSON document; omit or use '-' to read stdin",
    )
    args = parser.parse_args(argv)

    try:
        text = stdin.read() if args.file == "-" else Path(args.file).read_text()
    except OSError as err:
        print(f"gridfind: {err}", file=sys.stderr)
        return 2

    if not text.strip():
        parser.print_usage(sys.stderr)
        return 2

    try:
        result = _verdict_of(text)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as err:
        print(f"gridfind: invalid puzzle document: {err}", file=sys.stderr)
        return 2

    print(result.kind)
    if result.kind == "found" and result.witness is not None:
        print(_render_grid(result.witness))
    return 0 if result.kind == "found" else 1


def _verdict_of(text: str) -> Verdict:
    doc = json.loads(text)
    puzzle = Puzzle.from_json(json.dumps(doc["puzzle"]))
    state = WorkingState.from_json(json.dumps(doc["working_state"]))
    return verdict(puzzle, state)


def _render_grid(witness: dict[str, int]) -> str:
    """The found witness as a 9x9 grid: nine rows of space-separated digits, a
    double space between the 3x3 box columns, a blank line between box rows."""
    lines: list[str] = []
    for r in range(1, 10):
        cells = [str(witness[f"R{r}C{c}"]) for c in range(1, 10)]
        groups = (cells[0:3], cells[3:6], cells[6:9])
        lines.append("  ".join(" ".join(g) for g in groups))
        if r in (3, 6):
            lines.append("")
    return "\n".join(lines)


def console_main() -> None:
    sys.exit(main(sys.argv[1:], sys.stdin))
