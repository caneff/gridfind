"""Unit coverage for `validate_witness`'s own boundary (issue #186): a
known-good rendered grid passes, and the same grid with a duplicate digit
punched into its first row fails — proving the validator actually checks
rather than just parsing."""

import json
import re
from pathlib import Path

from gridfind.puzzle import Puzzle, WorkingState
from gridfind.verdict import verdict
from gridfind.witness_validator import validate_witness

POPULATIONS_DIR = Path(__file__).parent / "populations"
FOUND_4X4_DOC = (
    POPULATIONS_DIR
    / "board-rows-distinct-cols-distinct-regions-distinct"
    / "found-legal-4x4-sudoku-partial.json"
)


def _load(path: Path) -> tuple[Puzzle, WorkingState]:
    doc = json.loads(path.read_text())
    puzzle = Puzzle.from_json(json.dumps(doc["puzzle"]))
    state = WorkingState.from_json(json.dumps(doc["working_state"]))
    return puzzle, state


def _duplicate_first_two_cells_in_first_row(rendered: str) -> str:
    """Break the Latin-square property of row 1 by overwriting its second
    cell's digit with its first cell's digit — same width (a 4x4's domain is
    single-digit), so only that one character changes."""
    lines = rendered.split("\n")
    row = lines[1]
    matches = list(re.finditer(r"\d", row))
    first_digit = row[matches[0].start()]
    second_start = matches[1].start()
    lines[1] = row[:second_start] + first_digit + row[second_start + 1 :]
    return "\n".join(lines)


def test_validate_witness_accepts_a_known_good_grid() -> None:
    puzzle, state = _load(FOUND_4X4_DOC)
    result = verdict(puzzle, state)
    assert result.witness is not None

    assert validate_witness(result.witness.render(), puzzle) is True


def test_validate_witness_rejects_a_row_with_a_duplicate_digit() -> None:
    puzzle, state = _load(FOUND_4X4_DOC)
    result = verdict(puzzle, state)
    assert result.witness is not None

    broken = _duplicate_first_two_cells_in_first_row(result.witness.render())

    assert validate_witness(broken, puzzle) is False
