import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gridfind.conftest import JIGSAW_TETROMINOES
from gridfind.engine import GridfindError, MalformedPuzzleError
from gridfind.layers import UnknownLayerError
from gridfind.layers.board import cell_address
from gridfind.layers.regions import box_regions
from gridfind.puzzle import (
    EMPTY,
    BareSCell,
    BareSingleton,
    Board,
    Candidate,
    Constraint,
    Given,
    HalfSCell,
    Placement,
    Puzzle,
    SCellPin,
    SDirective,
    SingletonPin,
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
    assert strict.reason is None


def test_verdict_found_returns_a_witness_consistent_with_the_given() -> None:
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == (5,)
    assert len(result.witness) == 81


def test_verdict_found_witness_carries_the_boards_own_grid_shape() -> None:
    # Self-describing: the witness carries the same grid board
    # registers, so a consumer lays it out without re-deriving addressing.
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle)

    assert result.witness is not None
    assert len(result.witness.grid) == 9
    assert all(len(row) == 9 for row in result.witness.grid)
    assert result.witness.grid[0][0] == "R1C1"


def test_verdict_found_witness_carries_the_boards_box_region_map() -> None:
    # A regions-distinct constraint with no matrix of its own resolves to the
    # board's box convention: a 9x9 draws nine 3x3 boxes.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="regions-distinct"),),
        givens=(Given(address="R1C1", digit=5),),
    )

    result = verdict(puzzle)

    assert result.witness is not None
    assert result.witness.region_map == box_regions(9, 3, 3)


def test_verdict_found_witness_draws_no_boxes_without_a_regions_constraint() -> None:
    # A boxed-size board that carries no regions-distinct rule is a Latin
    # square, not a sudoku — the witness must not draw box grid-lines the
    # solver never enforced. One whole-board region, so render draws only the
    # outer edge.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
        ),
        givens=(Given(address="R1C1", digit=5),),
    )

    result = verdict(puzzle)

    assert result.witness is not None
    assert len(result.witness.region_map) == 1
    assert len(result.witness.region_map[0]) == 81


def test_verdict_found_witness_falls_back_to_one_region_with_no_convention() -> None:
    # A 5x5 board has no classic box convention (BOX_SHAPE) and no
    # regions-distinct constraint of its own, so the witness carries one
    # region covering the whole board — render then draws just the outer
    # edge, nothing interior.
    puzzle = Puzzle(
        board=Board(size=5),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
        ),
    )

    result = verdict(puzzle)

    assert result.witness is not None
    assert len(result.witness.region_map) == 1
    assert len(result.witness.region_map[0]) == 25


def test_verdict_found_witness_carries_a_supplied_jigsaw_partition() -> None:
    # A hand-built jigsaw partition (params["regions"]) rides
    # through to the witness as the region map it renders against, not the
    # board's box default.
    labels = [
        0,
        0,
        1,
        1,
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
        2,
        2,
        3,
        3,
    ]
    puzzle = Puzzle(
        board=Board(size=4),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct", params={"regions": labels}),
        ),
    )

    result = verdict(puzzle)

    assert result.witness is not None
    resolved = {frozenset(group) for group in result.witness.region_map}
    assert resolved == {
        frozenset({(1, 1), (1, 2), (2, 1), (2, 2)}),
        frozenset({(1, 3), (1, 4), (2, 3), (2, 4)}),
        frozenset({(3, 1), (3, 2), (4, 1), (4, 2)}),
        frozenset({(3, 3), (3, 4), (4, 3), (4, 4)}),
    }


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


def test_verdict_broke_on_a_placement_outside_its_own_candidate_set() -> None:
    puzzle = Puzzle(board=BOARD)
    state = WorkingState(
        places=(Placement(address="R2C2", digit=9),),
        candidates=(Candidate(address="R2C2", digits=frozenset({1, 2, 3})),),
    )

    result = verdict(puzzle, state)

    assert result.kind == "broke"
    assert result.witness is None


def test_verdict_found_when_givens_a_placement_and_a_candidate_set_all_agree() -> None:
    puzzle = Puzzle(
        board=BOARD,
        givens=(Given(address="R1C1", digit=5), Given(address="R2C2", digit=7)),
    )
    state = WorkingState(
        places=(Placement(address="R4C4", digit=3),),
        candidates=(Candidate(address="R3C3", digits=frozenset({1, 2, 9})),),
    )

    result = verdict(puzzle, state)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == (5,)
    assert result.witness["R2C2"] == (7,)
    assert result.witness["R4C4"] == (3,)
    assert result.witness["R3C3"][0] in {1, 2, 9}


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
    assert all(1 <= value[0] <= size for value in result.witness.assignment.values())


@pytest.mark.parametrize(
    ("size", "digit"),
    [pytest.param(4, 3, id="4x4-2x2-boxes"), pytest.param(6, 5, id="6x6-2x3-boxes")],
)
def test_sudoku_breaks_a_digit_repeat_within_one_box(size: int, digit: int) -> None:
    # R1C1 and R2C2 share a box at both sizes but no row and no column, so
    # rows/cols alone can't catch the repeat — only correct tiling does
    # (2x2 at 4x4, 2x3 at 6x6).
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
    assert all(1 <= value[0] <= size for value in result.witness.assignment.values())


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

    with pytest.raises(MalformedPuzzleError, match="off the board"):
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


def test_rows_distinct_breaks_a_repeat_forced_by_singleton_candidates() -> None:
    # No givens, no placements — the repeat is forced purely because both
    # cells' candidate sets have narrowed to the one digit.
    assert_layer_newly_breaks(
        (),
        (Constraint(type="rows-distinct"),),
        (),
        working_state=WorkingState(
            candidates=(
                Candidate(address="R4C2", digits=frozenset({6})),
                Candidate(address="R4C7", digits=frozenset({6})),
            )
        ),
    )


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


def test_line_count_distinct_breaks_when_a_full_row_has_too_few_distinct_digits() -> (
    None
):
    # Row 3's target is 3 distinct digits, but every cell is given as the
    # same digit — with the row already full, it can never reach the target
    # (the too-few direction the exceeds-target case above doesn't cover).
    assert_layer_newly_breaks(
        (),
        (Constraint(type="line-count-distinct"),),
        tuple(Given(address=f"R3C{c}", digit=1) for c in range(1, 10)),
    )


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


def _label_groups(size: int, labels: list[int]) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = {}
    for index, label in enumerate(labels):
        row, col = divmod(index, size)
        groups.setdefault(label, []).append(f"R{row + 1}C{col + 1}")
    return groups


def test_jigsaw_regions_distinct_found_with_a_connected_tetromino_partition() -> None:
    puzzle = Puzzle(
        board=Board(size=4),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct", params={"regions": JIGSAW_TETROMINOES}),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    for addresses in _label_groups(4, JIGSAW_TETROMINOES).values():
        digits = [result.witness[address] for address in addresses]
        assert len(set(digits)) == len(digits)


def test_jigsaw_regions_distinct_breaks_a_repeat_box_tiling_would_miss() -> None:
    # R1C1 and R4C4 share no row, no column, and no classic 2x2 box — only a
    # custom jigsaw region joining them catches the repeat.
    labels = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 0]

    assert_layer_newly_breaks(
        (Constraint(type="rows-distinct"), Constraint(type="cols-distinct")),
        (
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct", params={"regions": labels}),
        ),
        (Given(address="R1C1", digit=1), Given(address="R4C4", digit=1)),
        board=Board(size=4),
    )


def test_jigsaw_regions_distinct_with_an_over_large_region_returns_broke() -> None:
    # A region larger than the digit domain is unsolvable by pigeonhole —
    # broke, a satisfiability fact, never a validator's judgment.
    labels = [0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 3, 3, 2, 2, 3, 3]
    puzzle = Puzzle(
        board=Board(size=4),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct", params={"regions": labels}),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None
    assert result.reason == "region 1 holds 8 cells, domain is 4"


def test_jigsaw_regions_distinct_with_an_under_coverable_region_returns_broke() -> None:
    # A region with too few cells to cover the domain even doubled by
    # Schrodinger S-cells (domain > 2*cells) is unsolvable — broke,
    # symmetric to the over-sized pigeonhole case.
    labels = [0, 0, 0, *([1] * 33)]
    puzzle = Puzzle(
        board=Board(size=6, values=range(10)),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct", params={"regions": labels}),
            Constraint(type="schrodinger"),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None
    assert result.reason == "region 1 holds 3 cells, domain is 10 — too few to cover"


def _quattroquadri_box_labels(size: int) -> list[int]:
    box_span = size // 2
    return [
        (row // box_span) * 2 + (col // box_span)
        for row in range(size)
        for col in range(size)
    ]


def _quattroquadri_row_col_cages(size: int) -> tuple[Constraint, ...]:
    return tuple(
        Constraint(type="cage", params={"cells": group})
        for group in (*_rows(size), *_cols(size))
    )


def test_quattroquadri_found_over_a_6x6_grid_with_a_nine_digit_domain() -> None:
    # Ruleset 000EPV: four 3x3 boxes tile a 6x6 grid, each a
    # region covering the full 1-9 digit domain (cells == domain, the classic
    # no-S-cell edge of the cover band). Each 6-cell row/column may not repeat
    # but can never cover all 9 digits, so rows/cols are cages, not regions —
    # a domain-9-over-size-6 case the region/cage split exists for.
    size = 6
    labels = _quattroquadri_box_labels(size)
    puzzle = Puzzle(
        board=Board(size=size, values=range(1, 10)),
        constraints=(
            Constraint(type="regions-distinct", params={"regions": labels}),
            *_quattroquadri_row_col_cages(size),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    for addresses in _label_groups(size, labels).values():
        digits = [result.witness[address][0] for address in addresses]
        assert sorted(digits) == list(range(1, 10))
    for group in (*_rows(size), *_cols(size)):
        digits = [result.witness[address][0] for address in group]
        assert len(set(digits)) == len(digits)


def test_quattroquadri_breaks_on_a_digit_repeated_within_one_box() -> None:
    # R1C1 and R2C2 share no row and no column, so the row/col cages alone
    # allow both to hold 5 — only the box region (the regions-distinct layer)
    # catches the repeat.
    size = 6
    labels = _quattroquadri_box_labels(size)
    row_col_cages = _quattroquadri_row_col_cages(size)

    boxes_constraint = Constraint(type="regions-distinct", params={"regions": labels})
    assert_layer_newly_breaks(
        row_col_cages,
        (*row_col_cages, boxes_constraint),
        (Given(address="R1C1", digit=5), Given(address="R2C2", digit=5)),
        board=Board(size=size, values=range(1, 10)),
    )


def _killer_cage(cells: tuple[str, ...], total: int) -> tuple[Constraint, Constraint]:
    """A killer cage's recomposition (spec #240): a no-repeats `cage` plus the
    total as a `group-sum`, both over the same cells."""
    return (
        Constraint(type="cage", params={"cells": list(cells)}),
        Constraint(type="group-sum", params={"cells": list(cells), "sum": total}),
    )


def test_killer_cage_satisfiable_resolves_found() -> None:
    cells = ("R1C1", "R1C2", "R1C3")
    puzzle = Puzzle(
        board=BOARD,
        constraints=_killer_cage(cells, 6),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    digits = [result.witness[address][0] for address in cells]
    assert sum(digits) == 6
    assert len(set(digits)) == len(digits)


def test_killer_cage_forced_repeat_resolves_broke() -> None:
    # 1 + 1 meets the total but repeats a digit — the cage's no-repeats half
    # breaks it even though the sum alone would be satisfied, proving the
    # two composed rules both bind.
    puzzle = Puzzle(
        board=BOARD,
        constraints=_killer_cage(("R1C1", "R1C2"), 2),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_killer_cage_unreachable_total_resolves_broke() -> None:
    # Two distinct 1-9 digits reach at most 17; 30 is unreachable.
    puzzle = Puzzle(board=BOARD, constraints=_killer_cage(("R1C1", "R1C2"), 30))

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_killer_cage_sum_over_an_s_cell_reads_the_value_seam() -> None:
    # A killer cage on a Schrödinger board no longer refuses: its group-sum
    # half reads each cell's value through `value_expr`, so an S-cell folds in
    # as its `s_value` rather than raising "not Schrödinger-ready". The cage
    # completes (the value-seam reading proven discriminatingly at the
    # `group-sum` engine seam).
    puzzle = Puzzle(
        board=Board(size=4, values=range(5)),
        constraints=(
            Constraint(type="schrodinger"),
            *_killer_cage(("R1C1", "R1C2"), 3),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None


def test_schrodinger_ordinary_broke_with_in_band_regions_carries_no_reason() -> None:
    # A contradiction unrelated to region sizing (two conflicting givens on
    # one cell) must not get blamed on a region that is well within the
    # cover band (no false region-blame). Two
    # givens, not a given/placement pair: a placement refines to
    # d ∈ content on a Schrödinger board, so a given=1/placement=2 pair here
    # would resolve (2 lands on d1, R1C1 becomes the S-cell {1, 2}) rather
    # than conflict — givens stay literal d0 = d, so two of them on one
    # address are a genuine, schrodinger-independent contradiction.
    puzzle = Puzzle(
        board=Board(size=4, values=range(6)),
        constraints=(Constraint(type="sudoku"), Constraint(type="schrodinger")),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C1", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.reason is None


@given(length=st.integers(min_value=0, max_value=30).filter(lambda n: n != 16))
def test_verdict_rejects_a_regions_matrix_of_the_wrong_length(length: int) -> None:
    constraint = Constraint(type="regions-distinct", params={"regions": [0] * length})
    puzzle = Puzzle(board=Board(size=4), constraints=(constraint,))

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


@given(
    index=st.integers(min_value=0, max_value=15),
    bad_value=st.one_of(st.text(), st.floats(allow_nan=False), st.none()),
)
def test_verdict_rejects_a_regions_matrix_with_a_non_integer_entry(
    index: int, bad_value: object
) -> None:
    labels: list[object] = [0] * 16
    labels[index] = bad_value
    constraint = Constraint(type="regions-distinct", params={"regions": labels})
    puzzle = Puzzle(board=Board(size=4), constraints=(constraint,))

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


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
# between them — generalized over start/count/step rather than fixed at
# 2, 4, 6, 8.
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
    assert {value[0] for value in result.witness.assignment.values()} <= set(
        board.values
    )


def _rows(size: int) -> list[list[str]]:
    return [
        [cell_address(r, c) for c in range(1, size + 1)] for r in range(1, size + 1)
    ]


def _cols(size: int) -> list[list[str]]:
    return [list(col) for col in zip(*_rows(size), strict=True)]


def _boxes(size: int, box_rows: int, box_cols: int) -> list[list[str]]:
    return [
        [cell_address(row, col) for row, col in group]
        for group in box_regions(size, box_rows, box_cols)
    ]


@pytest.mark.parametrize(
    ("size", "values", "box_shape", "expected_s_cells"),
    [
        pytest.param(9, range(10), (3, 3), 1, id="9x9-digits-0-9"),
        pytest.param(6, range(1, 10), (2, 3), 3, id="6x6-digits-1-9"),
        pytest.param(4, range(8), (2, 2), 4, id="4x4-digits-0-7-domain-eq-2x-cells"),
    ],
)
def test_schrodinger_finds_the_forced_s_cell_count_per_house(
    size: int, values: range, box_shape: tuple[int, int], expected_s_cells: int
) -> None:
    # S-cell-ness discovered from givens alone — none stated here:
    # k = len(values) - size S-cells per row, column, and box.
    puzzle = Puzzle(
        board=Board(size=size, values=values),
        constraints=(Constraint(type="sudoku"), Constraint(type="schrodinger")),
    )

    result = verdict(puzzle, time_limit_s=30.0)

    assert result.kind == "found"
    witness = result.witness
    assert witness is not None
    for group in (*_rows(size), *_cols(size), *_boxes(size, *box_shape)):
        s_cells = sum(1 for address in group if len(witness[address]) == 2)
        assert s_cells == expected_s_cells


def test_schrodinger_with_values_not_exceeding_size_is_malformed() -> None:
    # len(values) == size forces no S-cell at all — refused before classify,
    # not silently accepted as a degenerate classic sudoku.
    puzzle = Puzzle(
        board=Board(size=9),  # default values 1-9, len == size
        constraints=(Constraint(type="schrodinger"),),
    )

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


def test_schrodinger_with_values_more_than_twice_size_is_broke() -> None:
    # Over 2*size digits can't fit even every cell doubled up — a genuine
    # infeasibility, not a special refusal.
    puzzle = Puzzle(
        board=Board(size=4, values=range(10)),  # 10 values, 2*size == 8
        constraints=(Constraint(type="schrodinger"), Constraint(type="rows-distinct")),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_schrodinger_puzzle_with_no_schrodinger_constraint_keeps_singleton_cells() -> (
    None
):
    # An ordinary puzzle's witness stays every cell a 1-tuple.
    puzzle = Puzzle(board=Board(size=4), constraints=(Constraint(type="sudoku"),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert all(len(value) == 1 for value in result.witness.assignment.values())


# A Schrödinger board small enough to solve fast: 5 digits (0-4) over a 4-cell
# row forces exactly one S-cell per row (k = len(values) - size = 1), columns
# left free. `rows-distinct` + `schrodinger` is the leanest stack that makes a
# pin honored or broke by the S-cell axis.
S_BOARD = Board(size=4, values=range(5))
S_CONSTRAINTS = (Constraint(type="rows-distinct"), Constraint(type="schrodinger"))

# Pinning R1C2..R1C4 as three distinct singletons forces R1C1 to be row 1's one
# S-cell, holding the two digits left over ({0, 4}).
_FORCE_R1C1_S = (
    SingletonPin(address="R1C2", digit=1),
    SingletonPin(address="R1C3", digit=2),
    SingletonPin(address="R1C4", digit=3),
)


@pytest.mark.parametrize(
    ("directives", "expected"),
    [
        pytest.param(
            (SingletonPin(address="R1C1", digit=0),),
            "found",
            id="singleton-pin-honored",
        ),
        pytest.param(
            (*_FORCE_R1C1_S, SingletonPin(address="R1C1", digit=0)),
            "broke",
            id="singleton-pin-broke-when-forced-s",
        ),
        pytest.param(
            (SCellPin(address="R1C1", pair=frozenset({0, 4})),),
            "found",
            id="s-cell-pin-honored",
        ),
        pytest.param(
            (*_FORCE_R1C1_S, SCellPin(address="R1C1", pair=frozenset({0, 1}))),
            "broke",
            id="s-cell-pin-broke-when-pair-cant-fit",
        ),
    ],
)
def test_verdict_applies_a_schrodinger_pin(
    directives: tuple[SDirective, ...], expected: str
) -> None:
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(s_directives=directives)

    result = verdict(puzzle, state)

    assert result.kind == expected


@pytest.mark.parametrize(
    "directive",
    [
        pytest.param(SingletonPin(address="R1C1", digit=9), id="singleton"),
        pytest.param(SCellPin(address="R1C1", pair=frozenset({0, 9})), id="s-cell"),
    ],
)
def test_verdict_rejects_a_pin_digit_outside_the_boards_values(
    directive: SDirective,
) -> None:
    # Asserted on a board that *has* the schrodinger layer, so only the
    # out-of-domain guard can fire — 9 is outside 0-4.
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(s_directives=(directive,))

    with pytest.raises(MalformedPuzzleError, match="9"):
        verdict(puzzle, state)


@pytest.mark.parametrize(
    "directive",
    [
        pytest.param(SingletonPin(address="R1C1", digit=1), id="singleton"),
        pytest.param(SCellPin(address="R1C1", pair=frozenset({1, 2})), id="s-cell"),
    ],
)
def test_verdict_rejects_a_pin_with_no_schrodinger_layer(directive: SDirective) -> None:
    # Uses an *in-domain* digit (1-2 on a 4x4's 1-4), so only the missing-layer
    # guard can fire — and it runs before the digit check.
    puzzle = Puzzle(
        board=Board(size=4), constraints=(Constraint(type="rows-distinct"),)
    )
    state = WorkingState(s_directives=(directive,))

    with pytest.raises(MalformedPuzzleError, match="schrodinger"):
        verdict(puzzle, state)


def test_verdict_ignores_empty_s_directives_on_a_non_schrodinger_puzzle() -> None:
    # An empty s_directives tuple is a no-op — the missing-layer
    # guard fires only when a pin is actually present.
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle, WorkingState(s_directives=()))

    assert result.kind == "found"


def test_verdict_runs_a_first_light_singleton_and_s_cell_pin_end_to_end() -> None:
    # The tracer's headline: a puzzle stating just a singleton pin
    # and an S-cell pin runs the whole path to a verdict.
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(
        s_directives=(
            SingletonPin(address="R1C1", digit=0),
            SCellPin(address="R2C2", pair=frozenset({0, 4})),
        )
    )

    result = verdict(puzzle, state)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == (0,)
    assert result.witness["R2C2"] == (0, 4)


@pytest.mark.parametrize(
    ("directives", "expected"),
    [
        pytest.param(
            (BareSingleton(address="R1C1"),),
            "found",
            id="bare-singleton-honored",
        ),
        pytest.param(
            (*_FORCE_R1C1_S, BareSingleton(address="R1C1")),
            "broke",
            id="bare-singleton-broke-when-forced-s",
        ),
        pytest.param(
            (BareSCell(address="R1C1"),),
            "found",
            id="bare-s-cell-honored",
        ),
        pytest.param(
            (BareSCell(address="R1C1"), BareSCell(address="R1C2")),
            "broke",
            id="bare-s-cell-broke-when-two-in-one-house",
        ),
        pytest.param(
            (HalfSCell(address="R1C1", digit=0),),
            "found",
            id="half-s-cell-honored",
        ),
        pytest.param(
            (*_FORCE_R1C1_S, HalfSCell(address="R1C1", digit=1)),
            "broke",
            id="half-s-cell-broke-when-digit-cant-fit",
        ),
    ],
)
def test_verdict_applies_a_bare_or_half_directive(
    directives: tuple[SDirective, ...], expected: str
) -> None:
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(s_directives=directives)

    result = verdict(puzzle, state)

    assert result.kind == expected


def test_verdict_half_s_cell_witness_is_an_s_cell_holding_the_digit() -> None:
    # A half S-cell honored means the cell resolves to an S-cell (a 2-tuple)
    # whose pair contains the named digit — proving the membership constraint
    # bit, not just that the puzzle happened to solve.
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(s_directives=(HalfSCell(address="R1C1", digit=0),))

    result = verdict(puzzle, state)

    assert result.kind == "found"
    assert result.witness is not None
    content = result.witness["R1C1"]
    assert len(content) == 2
    assert 0 in content


def test_verdict_half_s_cell_honors_a_digit_in_the_upper_slot() -> None:
    # Membership is "digit in EITHER slot", not just d0: force R1C1 to be the
    # S-cell holding {0, 4} (so d0=0, d1=4), then a half S-cell naming 4 — the
    # *upper* digit — is honored, proving the OR reaches d1.
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(
        s_directives=(*_FORCE_R1C1_S, HalfSCell(address="R1C1", digit=4))
    )

    result = verdict(puzzle, state)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == (0, 4)


def test_verdict_breaks_a_placement_absent_from_the_s_cells_content() -> None:
    # The membership OR is real, not vacuous: force R1C1 to the S-cell {0, 4}
    # and place a digit no completion can put there (1, already forced onto
    # R1C2) — no slot can hold it, so the placement is broke.
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(
        s_directives=_FORCE_R1C1_S, places=(Placement(address="R1C1", digit=1),)
    )

    result = verdict(puzzle, state)

    assert result.kind == "broke"


def test_verdict_given_vs_placement_diverge_on_an_s_cells_upper_digit() -> None:
    # The headline divergence: on a Schrödinger board a placement refines
    # to d ∈ content but a given stays literal d0 = d (CONTEXT.md's given /
    # placement glossary entries). Force R1C1 to the S-cell {0, 4} (a=0 <
    # b=4): a placement of b is honored (the upper-digit test above), a
    # given of b is broke since it forces d0 == 4 against the forced d0 == 0.
    puzzle = Puzzle(
        board=S_BOARD,
        constraints=S_CONSTRAINTS,
        givens=(Given(address="R1C1", digit=4),),
    )
    state = WorkingState(s_directives=_FORCE_R1C1_S)

    result = verdict(puzzle, state)

    assert result.kind == "broke"


def test_verdict_rejects_an_out_of_domain_placement_on_a_schrodinger_board() -> None:
    # The digit-range refusal must survive the rewrite
    # to d ∈ content, on a board that actually has the schrodinger layer
    # (9 is outside 0-4) — not just the pre-existing non-schrodinger case.
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(places=(Placement(address="R1C1", digit=9),))

    with pytest.raises(MalformedPuzzleError, match=r"9.*R1C1"):
        verdict(puzzle, state)


def test_verdict_rejects_a_half_s_cell_digit_outside_the_boards_values() -> None:
    # A half S-cell names a digit, so it inherits the out-of-domain guard —
    # asserted on a board that has the schrodinger layer so only that guard
    # can fire (9 is outside 0-4).
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(s_directives=(HalfSCell(address="R1C1", digit=9),))

    with pytest.raises(MalformedPuzzleError, match="9"):
        verdict(puzzle, state)


def test_verdict_honors_a_placement_landing_on_an_s_cells_upper_digit() -> None:
    # A placement refines to d ∈ content on a Schrödinger board,
    # so it survives landing on the *upper* slot of a forced S-cell — not
    # just d0. Force R1C1 to the S-cell {0, 4} (d0=0, d1=4), then place the
    # upper digit 4: a literal d0 == 4 would break this, a bare placement
    # honors it.
    puzzle = Puzzle(board=S_BOARD, constraints=S_CONSTRAINTS)
    state = WorkingState(
        s_directives=_FORCE_R1C1_S, places=(Placement(address="R1C1", digit=4),)
    )

    result = verdict(puzzle, state)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == (0, 4)


def test_verdict_found_witness_carries_no_modifiers_without_a_modifier_layer() -> None:
    # An ordinary puzzle has no `is_modifier` structure to report from, so
    # the witness's modifiers field is empty rather than absent.
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness.modifiers == {}


def test_verdict_found_witness_reports_every_discovered_doubler_as_doubler() -> None:
    # One-per-house (spec #232 decision #222) puts exactly `size` discovered
    # modifiers on a bare doubler puzzle — one per row — each named "doubler",
    # the modifier's own declared type.
    puzzle = Puzzle(board=BOARD, constraints=(Constraint(type="doubler"),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness.modifiers) == BOARD.size
    assert set(result.witness.modifiers.values()) == {"doubler"}
    assert set(result.witness.modifiers).issubset(result.witness.assignment)


def test_verdict_found_witness_names_the_cell_a_sum_forces_to_discover() -> None:
    # 19 exceeds the max of two plain 1-9 digits (18), so the group-sum clue
    # is only reachable by discovering a doubler in R1C1 or R1C2 (mirrors
    # group_sum_test.py's engine-seam version of this same forcing).
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="doubler"),
            Constraint(type="group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 19}),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    discovered = set(result.witness.modifiers) & {"R1C1", "R1C2"}
    assert len(discovered) == 1
    assert result.witness.modifiers[discovered.pop()] == "doubler"


def test_verdict_given_on_a_modified_cell_pins_the_digit_value_derives() -> None:
    # A given writes d0 = 5 (never the value); 15 is only reachable if that
    # digit is discovered as a doubler and read as 10 by the group-sum, so
    # R1C2 must land on 5 (10 + 5), not 10 (5 + 10 is off the board anyway).
    # This proves the clue read the *derived* value while the given kept the
    # witness's own digit untouched (spec #232 decision #218).
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="doubler"),
            Constraint(type="group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 15}),
        ),
        givens=(Given(address="R1C1", digit=5),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == (5,)
    assert result.witness.modifiers["R1C1"] == "doubler"
    assert result.witness["R1C2"] == (5,)
