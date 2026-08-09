import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gridfind.engine import GridfindError, MalformedPuzzleError
from gridfind.layers import UnknownLayerError
from gridfind.puzzle import (
    EMPTY,
    Board,
    Candidate,
    Constraint,
    Given,
    Placement,
    Puzzle,
    WorkingState,
)
from gridfind.verdict import verdict

BOARD = Board(size=9)


def assert_layer_newly_breaks(
    smaller: tuple[Constraint, ...],
    full: tuple[Constraint, ...],
    givens: tuple[Given, ...],
    working_state: WorkingState = EMPTY,
    board: Board = BOARD,
) -> None:
    """The full constraint set newly breaks a state the smaller set allows.

    Two puzzles differing only by which constraints they include, sharing
    one set of givens and one working state — given once here. The whole point:
    the two copies can no longer drift apart by hand and pass while testing
    nothing.
    """
    lenient = verdict(
        Puzzle(board=board, constraints=smaller, givens=givens), working_state
    )
    assert lenient.kind != "broke"

    strict = verdict(
        Puzzle(board=board, constraints=full, givens=givens), working_state
    )
    assert strict.kind == "broke"
    assert strict.witness is None


def test_verdict_found_returns_a_witness_consistent_with_the_given() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == 5
    assert len(result.witness) == 81


def test_verdict_found_witness_carries_the_boards_own_grid_shape() -> None:
    # Self-describing (issue #72): the witness carries the same grid board
    # registers, so a consumer lays it out without re-deriving addressing.
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle)

    assert result.witness is not None
    assert len(result.witness.grid) == 9
    assert all(len(row) == 9 for row in result.witness.grid)
    assert result.witness.grid[0][0] == "R1C1"


def test_verdict_broke_on_a_given_place_conflict() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))
    state = WorkingState(places=(Placement(address="R1C1", digit=6),))

    result = verdict(puzzle, state)

    assert result.kind == "broke"
    assert result.witness is None


def test_verdict_broke_on_a_candidate_excluding_the_given() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))
    state = WorkingState(
        candidates=(Candidate(address="R1C1", digits=frozenset({1, 2, 3})),)
    )

    result = verdict(puzzle, state)

    assert result.kind == "broke"
    assert result.witness is None


def test_verdict_unknown_when_the_budget_is_exhausted() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle, time_limit_s=0.0)

    assert result.kind == "unknown"
    assert result.witness is None


def test_verdict_defaults_to_the_empty_working_state() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    assert verdict(puzzle).kind == "found"


@pytest.mark.parametrize("size", [6, 4], ids=["6x6", "4x4"])
def test_verdict_found_on_a_board_keeps_every_witness_digit_in_1_to_n(
    size: int,
) -> None:
    puzzle = Puzzle(
        board=Board(size=size),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
        ),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness) == size * size
    assert all(1 <= value <= size for value in result.witness.assignment.values())


@pytest.mark.parametrize(
    ("size", "digit"),
    [pytest.param(4, 3, id="4x4-2x2-boxes"), pytest.param(6, 5, id="6x6-2x3-boxes")],
)
def test_sudoku_breaks_a_digit_repeat_within_one_box(size: int, digit: int) -> None:
    # R1C1 and R2C2 share a box at both sizes but no row and no column, so
    # rows/cols alone can't catch the repeat — only correct tiling does
    # (2x2 at 4x4, 2x3 at 6x6; issue #79).
    assert_layer_newly_breaks(
        (Constraint(type="rows-distinct"), Constraint(type="cols-distinct")),
        (
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct"),
        ),
        (Given(address="R1C1", digit=digit), Given(address="R2C2", digit=digit)),
        board=Board(size=size),
    )


@pytest.mark.parametrize("size", [pytest.param(4, id="4x4"), pytest.param(6, id="6x6")])
def test_sudoku_found_on_a_legal_board(size: int) -> None:
    puzzle = Puzzle(
        board=Board(size=size),
        constraints=(Constraint(type="sudoku"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C4", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness) == size * size
    assert all(1 <= value <= size for value in result.witness.assignment.values())


def test_regions_distinct_on_a_5x5_board_refuses_with_a_gridfind_error() -> None:
    puzzle = Puzzle(
        board=Board(size=5), constraints=(Constraint(type="regions-distinct"),)
    )

    with pytest.raises(GridfindError):
        verdict(puzzle)


def test_rows_and_cols_distinct_on_a_5x5_board_builds_and_solves() -> None:
    # The other half of the test above: only `regions-distinct` needs a box
    # convention, and 5x5 has none. Rows and cols ask for no boxes, so a 5x5
    # is an ordinary Latin square and completes.
    puzzle = Puzzle(
        board=Board(size=5),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness) == 25


def test_verdict_rejects_an_off_board_address() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R10C1", digit=5),))

    with pytest.raises(ValueError, match="off the board"):
        verdict(puzzle)


@pytest.mark.parametrize(
    ("size", "digit"),
    [pytest.param(9, 42, id="9x9"), pytest.param(6, 7, id="6x6")],
)
def test_verdict_rejects_a_given_digit_outside_the_boards_values(
    size: int, digit: int
) -> None:
    # Each board refuses against *its own* range, not a borrowed 1-9: 7 is a
    # legal digit at 9x9 and out of range at 6x6. A malformed puzzle raises
    # rather than answering broke — it has not earned that consistency claim.
    puzzle = Puzzle(
        board=Board(size=size), givens=(Given(address="R1C1", digit=digit),)
    )

    with pytest.raises(MalformedPuzzleError, match=f"{digit}.*R1C1"):
        verdict(puzzle)


def test_verdict_rejects_a_placement_digit_outside_the_boards_values() -> None:
    state = WorkingState(places=(Placement(address="R1C1", digit=42),))

    with pytest.raises(MalformedPuzzleError, match=r"42.*R1C1"):
        verdict(Puzzle(board=BOARD), state)


def test_verdict_rejects_an_out_of_range_candidate_digit() -> None:
    state = WorkingState(
        candidates=(Candidate(address="R1C1", digits=frozenset({1, 42})),)
    )

    with pytest.raises(MalformedPuzzleError, match=r"42.*R1C1"):
        verdict(Puzzle(board=BOARD), state)


@pytest.mark.parametrize("size", [9, 6], ids=["9x9", "6x6"])
def test_rows_distinct_breaks_a_row_repeat_that_board_alone_would_not(
    size: int,
) -> None:
    assert_layer_newly_breaks(
        (),
        (Constraint(type="rows-distinct"),),
        (Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
        board=Board(size=size),
    )


def test_rows_distinct_found_when_no_row_repeats() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="rows-distinct"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_line_count_distinct_breaks_when_a_row_already_exceeds_its_target() -> None:
    assert_layer_newly_breaks(
        (),
        (Constraint(type="line-count-distinct"),),
        (
            Given(address="R2C1", digit=1),
            Given(address="R2C2", digit=2),
            Given(address="R2C3", digit=3),
        ),
    )


def test_line_count_distinct_found_when_row_counts_are_satisfiable() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="line-count-distinct"),),
        givens=(Given(address="R1C1", digit=4), Given(address="R1C2", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len({result.witness[f"R1C{c}"] for c in range(1, 10)}) == 1


@pytest.mark.parametrize("size", [9, 6], ids=["9x9", "6x6"])
def test_cols_distinct_breaks_a_col_repeat_that_board_alone_would_not(
    size: int,
) -> None:
    assert_layer_newly_breaks(
        (),
        (Constraint(type="cols-distinct"),),
        (Given(address="R1C1", digit=5), Given(address="R2C1", digit=5)),
        board=Board(size=size),
    )


def test_cols_distinct_found_when_no_col_repeats() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="cols-distinct"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R2C1", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_latin_square_broke_on_a_column_repeat_rows_distinct_alone_misses() -> None:
    assert_layer_newly_breaks(
        (Constraint(type="rows-distinct"),),
        (Constraint(type="rows-distinct"), Constraint(type="cols-distinct")),
        (Given(address="R1C1", digit=5), Given(address="R5C1", digit=5)),
    )


def test_latin_square_found_on_a_legal_partial() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
        ),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=2),
            Given(address="R2C1", digit=2),
            Given(address="R2C2", digit=1),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_constraint_order_does_not_change_the_verdict() -> None:
    givens = (Given(address="R1C1", digit=5), Given(address="R5C1", digit=5))
    forward = (Constraint(type="rows-distinct"), Constraint(type="cols-distinct"))
    reversed_order = (
        Constraint(type="cols-distinct"),
        Constraint(type="rows-distinct"),
    )

    a = verdict(Puzzle(board=BOARD, constraints=forward, givens=givens))
    b = verdict(Puzzle(board=BOARD, constraints=reversed_order, givens=givens))

    assert a.kind == b.kind == "broke"


def test_regions_distinct_breaks_a_box_repeat_rows_and_cols_distinct_miss() -> None:
    assert_layer_newly_breaks(
        (Constraint(type="rows-distinct"), Constraint(type="cols-distinct")),
        (
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct"),
        ),
        (Given(address="R1C1", digit=5), Given(address="R2C2", digit=5)),
    )


def test_regions_distinct_found_when_no_box_repeats() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct"),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R4C4", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_sudoku_preset_matches_the_explicit_three_distinct_constraints() -> None:
    givens = (Given(address="R1C1", digit=5), Given(address="R2C2", digit=5))
    explicit = (
        Constraint(type="rows-distinct"),
        Constraint(type="cols-distinct"),
        Constraint(type="regions-distinct"),
    )

    preset_result = verdict(
        Puzzle(board=BOARD, constraints=(Constraint(type="sudoku"),), givens=givens)
    )
    explicit_result = verdict(Puzzle(board=BOARD, constraints=explicit, givens=givens))

    assert preset_result.kind == explicit_result.kind == "broke"


def test_sudoku_preset_found_on_a_legal_partial() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="sudoku"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R4C4", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_verdict_rejects_an_unknown_constraint_type() -> None:
    puzzle = Puzzle(board=BOARD, constraints=(Constraint(type="not-a-real-rule"),))

    with pytest.raises(UnknownLayerError):
        verdict(puzzle)


# A stepped range (step >= 2) so the board's values genuinely have gaps
# between them — the regression's shape, generalized over start/count/step
# rather than fixed at 2, 4, 6, 8.
STEPPED_VALUES = st.builds(
    lambda start, count, step: range(start, start + count * step, step),
    st.integers(1, 5),
    st.integers(2, 6),
    st.integers(2, 3),
)
STEPPED_BOARDS = st.builds(Board, size=st.sampled_from([4, 6]), values=STEPPED_VALUES)


@given(board=STEPPED_BOARDS)
@settings(max_examples=50)
def test_verdict_found_witness_only_holds_a_boards_declared_digits(
    board: Board,
) -> None:
    result = verdict(Puzzle(board=board))

    assert result.kind == "found"
    assert result.witness is not None
    assert set(result.witness.assignment.values()) <= set(board.values)
