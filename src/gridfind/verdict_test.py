import pytest

from gridfind.engine import GridfindError
from gridfind.layers import UnknownLayerError
from gridfind.puzzle import (
    EMPTY,
    Board,
    Candidate,
    Given,
    Place,
    Puzzle,
    Variant,
    WorkingState,
)
from gridfind.verdict import verdict

BOARD = Board(size=9)


def assert_layer_newly_breaks(
    smaller: tuple[Variant, ...],
    full: tuple[Variant, ...],
    givens: tuple[Given, ...],
    working_state: WorkingState = EMPTY,
    board: Board = BOARD,
) -> None:
    """The full record set newly breaks a state the smaller set still allows.

    Two puzzles differing only by which variant records they include, sharing
    one set of givens and one working state — given once here. The whole point:
    the two copies can no longer drift apart by hand and pass while testing
    nothing.
    """
    lenient = verdict(
        Puzzle(board=board, variants=smaller, givens=givens), working_state
    )
    assert lenient.kind != "broke"

    strict = verdict(Puzzle(board=board, variants=full, givens=givens), working_state)
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
    state = WorkingState(places=(Place(address="R1C1", digit=6),))

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


def test_verdict_found_on_a_6x6_board_keeps_every_witness_digit_in_1_to_6() -> None:
    puzzle = Puzzle(
        board=Board(size=6),
        variants=(Variant(type="rows-distinct"), Variant(type="cols-distinct")),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness) == 36
    assert all(1 <= value <= 6 for value in result.witness.values.values())


def test_verdict_found_on_a_4x4_board_keeps_every_witness_digit_in_1_to_4() -> None:
    puzzle = Puzzle(
        board=Board(size=4),
        variants=(Variant(type="rows-distinct"), Variant(type="cols-distinct")),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness) == 16
    assert all(1 <= value <= 4 for value in result.witness.values.values())


def test_sudoku_on_a_6x6_breaks_a_digit_repeat_within_one_2x3_box() -> None:
    # rows/cols alone wouldn't catch a same-box repeat two rows/cols apart —
    # only correct 2x3 tiling does (issue #77).
    assert_layer_newly_breaks(
        (Variant(type="rows-distinct"), Variant(type="cols-distinct")),
        (
            Variant(type="rows-distinct"),
            Variant(type="cols-distinct"),
            Variant(type="regions-distinct"),
        ),
        (Given(address="R1C1", digit=5), Given(address="R2C2", digit=5)),
        board=Board(size=6),
    )


def test_sudoku_found_on_a_legal_6x6() -> None:
    puzzle = Puzzle(
        board=Board(size=6),
        variants=(Variant(type="sudoku"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C4", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert all(1 <= value <= 6 for value in result.witness.values.values())


def test_regions_distinct_on_a_5x5_board_refuses_with_a_gridfind_error() -> None:
    puzzle = Puzzle(board=Board(size=5), variants=(Variant(type="regions-distinct"),))

    with pytest.raises(GridfindError):
        verdict(puzzle)


def test_rows_and_cols_distinct_on_a_5x5_board_still_builds() -> None:
    puzzle = Puzzle(
        board=Board(size=5),
        variants=(Variant(type="rows-distinct"), Variant(type="cols-distinct")),
    )

    result = verdict(puzzle)

    assert result.kind in ("found", "broke", "unknown")


def test_verdict_rejects_a_given_digit_outside_a_6x6_boards_domain() -> None:
    puzzle = Puzzle(board=Board(size=6), givens=(Given(address="R1C1", digit=7),))

    with pytest.raises(ValueError, match="out of range"):
        verdict(puzzle)


def test_verdict_rejects_an_off_board_address() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R10C1", digit=5),))

    with pytest.raises(ValueError, match="off the board"):
        verdict(puzzle)


def test_verdict_rejects_an_out_of_range_given_digit() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=42),))

    with pytest.raises(ValueError, match="out of range"):
        verdict(puzzle)


def test_verdict_rejects_an_out_of_range_candidate_digit() -> None:
    state = WorkingState(
        candidates=(Candidate(address="R1C1", digits=frozenset({1, 42})),)
    )

    with pytest.raises(ValueError, match="out of range"):
        verdict(Puzzle(board=BOARD), state)


def test_rows_distinct_breaks_a_row_repeat_that_board_alone_would_not() -> None:
    assert_layer_newly_breaks(
        (),
        (Variant(type="rows-distinct"),),
        (Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
    )


def test_rows_distinct_found_when_no_row_repeats() -> None:
    puzzle = Puzzle(
        board=BOARD,
        variants=(Variant(type="rows-distinct"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_line_count_distinct_breaks_when_a_row_already_exceeds_its_target() -> None:
    assert_layer_newly_breaks(
        (),
        (Variant(type="line-count-distinct"),),
        (
            Given(address="R2C1", digit=1),
            Given(address="R2C2", digit=2),
            Given(address="R2C3", digit=3),
        ),
    )


def test_line_count_distinct_found_when_row_counts_are_satisfiable() -> None:
    puzzle = Puzzle(
        board=BOARD,
        variants=(Variant(type="line-count-distinct"),),
        givens=(Given(address="R1C1", digit=4), Given(address="R1C2", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len({result.witness[f"R1C{c}"] for c in range(1, 10)}) == 1


def test_cols_distinct_breaks_a_col_repeat_that_board_alone_would_not() -> None:
    assert_layer_newly_breaks(
        (),
        (Variant(type="cols-distinct"),),
        (Given(address="R1C1", digit=5), Given(address="R2C1", digit=5)),
    )


def test_cols_distinct_found_when_no_col_repeats() -> None:
    puzzle = Puzzle(
        board=BOARD,
        variants=(Variant(type="cols-distinct"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R2C1", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_latin_square_broke_on_a_column_repeat_rows_distinct_alone_misses() -> None:
    assert_layer_newly_breaks(
        (Variant(type="rows-distinct"),),
        (Variant(type="rows-distinct"), Variant(type="cols-distinct")),
        (Given(address="R1C1", digit=5), Given(address="R5C1", digit=5)),
    )


def test_latin_square_found_on_a_legal_partial() -> None:
    puzzle = Puzzle(
        board=BOARD,
        variants=(Variant(type="rows-distinct"), Variant(type="cols-distinct")),
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


def test_record_order_does_not_change_the_verdict() -> None:
    givens = (Given(address="R1C1", digit=5), Given(address="R5C1", digit=5))
    forward = (Variant(type="rows-distinct"), Variant(type="cols-distinct"))
    reversed_order = (Variant(type="cols-distinct"), Variant(type="rows-distinct"))

    a = verdict(Puzzle(board=BOARD, variants=forward, givens=givens))
    b = verdict(Puzzle(board=BOARD, variants=reversed_order, givens=givens))

    assert a.kind == b.kind == "broke"


def test_regions_distinct_breaks_a_box_repeat_rows_and_cols_distinct_miss() -> None:
    assert_layer_newly_breaks(
        (Variant(type="rows-distinct"), Variant(type="cols-distinct")),
        (
            Variant(type="rows-distinct"),
            Variant(type="cols-distinct"),
            Variant(type="regions-distinct"),
        ),
        (Given(address="R1C1", digit=5), Given(address="R2C2", digit=5)),
    )


def test_regions_distinct_found_when_no_box_repeats() -> None:
    puzzle = Puzzle(
        board=BOARD,
        variants=(
            Variant(type="rows-distinct"),
            Variant(type="cols-distinct"),
            Variant(type="regions-distinct"),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R4C4", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_sudoku_sugar_matches_the_explicit_three_distinct_records() -> None:
    givens = (Given(address="R1C1", digit=5), Given(address="R2C2", digit=5))
    explicit = (
        Variant(type="rows-distinct"),
        Variant(type="cols-distinct"),
        Variant(type="regions-distinct"),
    )

    sugar_result = verdict(
        Puzzle(board=BOARD, variants=(Variant(type="sudoku"),), givens=givens)
    )
    explicit_result = verdict(Puzzle(board=BOARD, variants=explicit, givens=givens))

    assert sugar_result.kind == explicit_result.kind == "broke"


def test_sudoku_sugar_found_on_a_legal_partial() -> None:
    puzzle = Puzzle(
        board=BOARD,
        variants=(Variant(type="sudoku"),),
        givens=(Given(address="R1C1", digit=1), Given(address="R4C4", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_verdict_rejects_an_unknown_variant_record_type() -> None:
    puzzle = Puzzle(board=BOARD, variants=(Variant(type="not-a-real-rule"),))

    with pytest.raises(UnknownLayerError):
        verdict(puzzle)
