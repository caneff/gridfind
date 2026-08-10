"""Unit coverage for `validate_witness`'s own boundary (issue #186, extended
#187): a known-good rendered grid passes, and the same grid with a duplicate
digit punched into its first row fails — proving the validator actually
checks rather than just parsing. Extended to a Schrödinger board (#187) to
pin the S-cell pair `{a b}` branch of the permutation check the same way."""

import json
import re
from pathlib import Path

from gridfind.puzzle import Board, Constraint, Puzzle, WorkingState
from gridfind.verdict import verdict
from gridfind.witness_validator import validate_witness

POPULATIONS_DIR = Path(__file__).parent / "populations"
FOUND_4X4_DOC = (
    POPULATIONS_DIR
    / "board-rows-distinct-cols-distinct-regions-distinct"
    / "found-legal-4x4-sudoku-partial.json"
)

# A 4x4 board with a 5-digit domain forces exactly one S-cell per row, column,
# and region (k = len(values) - size = 1) — small enough to solve fast while
# still exercising every group the permutation check walks.
SCHRODINGER_PUZZLE = Puzzle(
    board=Board(size=4, values=range(1, 6)),
    constraints=(
        Constraint(type="rows-distinct"),
        Constraint(type="cols-distinct"),
        Constraint(type="regions-distinct"),
        Constraint(type="schrodinger"),
    ),
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


def test_validate_witness_accepts_a_known_good_schrodinger_grid() -> None:
    result = verdict(SCHRODINGER_PUZZLE, time_limit_s=30.0)
    assert result.kind == "found"
    assert result.witness is not None

    assert validate_witness(result.witness.render(), SCHRODINGER_PUZZLE) is True


def test_validate_witness_rejects_a_schrodinger_grid_that_violates_the_reading() -> (
    None
):
    result = verdict(SCHRODINGER_PUZZLE, time_limit_s=30.0)
    assert result.witness is not None

    broken = _duplicate_first_two_cells_in_first_row(result.witness.render())

    assert validate_witness(broken, SCHRODINGER_PUZZLE) is False
