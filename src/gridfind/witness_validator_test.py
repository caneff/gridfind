"""Unit coverage for `validate_witness`'s own boundary: a known-good rendered
grid passes, and the same grid with a duplicate digit punched into its first
row fails — proving the validator actually checks rather than just parsing.
Extended to a Schrödinger board to pin the S-cell pair `{a b}` branch of the
permutation check the same way."""

import json
import re

from gridfind.conftest import FOUND_4X4_DOC, JIGSAW_TETROMINOES
from gridfind.puzzle import Board, Constraint, Puzzle, WorkingState
from gridfind.verdict import verdict
from gridfind.witness_validator import validate_witness

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

# A hand-built jigsaw partition (params["regions"]), the shape
# region_map_for_constraints' other branch resolves. Shared with
# verdict_test.py via conftest.py: it must be a genuine tetromino shape, not
# the box default FOUND_4X4_DOC and SCHRODINGER_PUZZLE both exercise, or a
# render/validate path that silently fell back to box tiling would still
# round-trip clean.
JIGSAW_PUZZLE = Puzzle(
    board=Board(size=4),
    constraints=(
        Constraint(type="rows-distinct"),
        Constraint(type="cols-distinct"),
        Constraint(type="regions-distinct", params={"regions": JIGSAW_TETROMINOES}),
    ),
)

# No regions-distinct constraint at all — the render path's one-whole-board
# fallback vs. the validator's skip-the-check branch.
LATIN_SQUARE_PUZZLE = Puzzle(
    board=Board(size=4),
    constraints=(Constraint(type="rows-distinct"), Constraint(type="cols-distinct")),
)

# Neither rows-distinct nor cols-distinct at all — a somedoku puzzle,
# which runs on `line-count-distinct` alone; its witness's
# rows/columns are deliberately not full permutations of the domain.
SOMEDOKU_PUZZLE = Puzzle(
    board=Board(size=4),
    constraints=(Constraint(type="line-count-distinct"),),
)


def _build(doc: dict[str, object]) -> tuple[Puzzle, WorkingState]:
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
    puzzle, state = _build(FOUND_4X4_DOC)
    result = verdict(puzzle, state)
    assert result.witness is not None

    assert validate_witness(result.witness.render(), puzzle) is True


def test_validate_witness_rejects_a_row_with_a_duplicate_digit() -> None:
    puzzle, state = _build(FOUND_4X4_DOC)
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


def test_validate_witness_round_trips_a_jigsaw_partition() -> None:
    # The render path and validate_witness both cross
    # region_map_for_constraints. A jigsaw regions-distinct constraint
    # (params["regions"], not the box default) proves they still resolve the
    # identical partition, not just the bare box case the other tests cover.
    result = verdict(JIGSAW_PUZZLE)
    assert result.kind == "found"
    assert result.witness is not None

    assert validate_witness(result.witness.render(), JIGSAW_PUZZLE) is True


def test_validate_witness_round_trips_a_board_with_no_regions_constraint() -> None:
    # With no regions-distinct constraint at all, the render path falls back
    # to one whole-board region for its box-line drawing while the validator
    # skips the region check entirely — both sides of that same
    # no-regions fallback must still agree the grid is legal.
    result = verdict(LATIN_SQUARE_PUZZLE)
    assert result.kind == "found"
    assert result.witness is not None

    assert validate_witness(result.witness.render(), LATIN_SQUARE_PUZZLE) is True


def test_validate_witness_round_trips_a_board_with_no_rows_or_cols_constraint() -> None:
    # With neither rows-distinct nor cols-distinct declared, the validator
    # must skip both permutation checks rather than wrongly reject a
    # somedoku witness whose rows/columns aren't full permutations of the
    # domain by design.
    result = verdict(SOMEDOKU_PUZZLE)
    assert result.kind == "found"
    assert result.witness is not None

    assert validate_witness(result.witness.render(), SOMEDOKU_PUZZLE) is True


def test_validate_witness_rejects_a_grid_missing_a_border_line() -> None:
    # A layout drift in Witness.render() that drops a line (e.g. a border
    # line lost off the end) must be caught against grid_text.py's named
    # line-count contract rather than silently reparsed as a
    # shorter, still-legal-looking grid.
    puzzle, state = _build(FOUND_4X4_DOC)
    result = verdict(puzzle, state)
    assert result.witness is not None

    lines = result.witness.render().split("\n")
    drifted = "\n".join(lines[:-1])

    assert validate_witness(drifted, puzzle) is False


def test_validate_witness_rejects_a_cell_line_carrying_an_extra_token() -> None:
    # A layout drift that puts an extra cell token on a row line (e.g. a
    # stray digit from a mis-widened column) violates grid_text.py's "size
    # tokens per cell line" contract — caught as a shape
    # mismatch, not silently accepted as one of the row's real cells.
    puzzle, state = _build(FOUND_4X4_DOC)
    result = verdict(puzzle, state)
    assert result.witness is not None

    lines = result.witness.render().split("\n")
    lines[1] += " 1"
    drifted = "\n".join(lines)

    assert validate_witness(drifted, puzzle) is False
