import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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
from gridfind.verdict import Witness, verdict

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
    # Self-describing (issue #72): the witness carries the same grid board
    # registers, so a consumer lays it out without re-deriving addressing.
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle)

    assert result.witness is not None
    assert len(result.witness.grid) == 9
    assert all(len(row) == 9 for row in result.witness.grid)
    assert result.witness.grid[0][0] == "R1C1"


def test_verdict_found_witness_carries_the_boards_box_region_map() -> None:
    # A regions-distinct constraint with no matrix of its own resolves to the
    # board's box convention (issue #124): a 9x9 draws nine 3x3 boxes.
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
    # A hand-built jigsaw partition (issue #123's params["regions"]) rides
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


def test_witness_render_draws_jigsaw_borders_between_regions() -> None:
    # Two single-column regions on a 2x2 board: a vertical divider runs the
    # full height, no horizontal divider — junctions resolved from whichever
    # arms actually meet (issue #124).
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (1,),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (4,),
    }
    region_map = [[(1, 1), (2, 1)], [(1, 2), (2, 2)]]
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == ("┌───┬───┐\n│ 1 │ 2 │\n│   │   │\n│ 3 │ 4 │\n└───┴───┘")


def test_witness_render_draws_classic_box_borders_for_a_box_partition() -> None:
    # Fed the classic box tiling, the same renderer draws the familiar 3x3-
    # style boxes — here a 4x4's 2x2 boxes — so box_shape's old banding is
    # subsumed, not regressed (issue #124).
    grid = [[f"R{r}C{c}" for c in range(1, 5)] for r in range(1, 5)]
    assignment: dict[str, tuple[int, ...]] = {
        address: (i % 9 + 1,) for i, row in enumerate(grid) for address in row
    }
    witness = Witness(grid=grid, assignment=assignment, region_map=box_regions(4, 2, 2))

    assert witness.render() == (
        "┌───────┬───────┐\n"
        "│ 1   1 │ 1   1 │\n"
        "│       │       │\n"
        "│ 2   2 │ 2   2 │\n"
        "├───────┼───────┤\n"
        "│ 3   3 │ 3   3 │\n"
        "│       │       │\n"
        "│ 4   4 │ 4   4 │\n"
        "└───────┴───────┘"
    )


def test_witness_render_draws_singleton_and_unequal_regions_correctly() -> None:
    # A singleton region beside an 8-cell region on a 3x3 board — no
    # nine-of-nine assumption (issue #124).
    grid = [[f"R{r}C{c}" for c in range(1, 4)] for r in range(1, 4)]
    assignment: dict[str, tuple[int, ...]] = {
        address: (i % 9 + 1,) for i, row in enumerate(grid) for address in row
    }
    region_map = [
        [(1, 1)],
        [(1, 2), (1, 3), (2, 1), (2, 2), (2, 3), (3, 1), (3, 2), (3, 3)],
    ]
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == (
        "┌───┬───────┐\n"
        "│ 1 │ 1   1 │\n"
        "├───┘       │\n"
        "│ 2   2   2 │\n"
        "│           │\n"
        "│ 3   3   3 │\n"
        "└───────────┘"
    )


def test_witness_render_draws_an_s_cell_as_a_curly_brace_pair() -> None:
    # An S-cell's pair (issue #141, decision #135) widens the whole witness —
    # every cell, singleton or not, right-pads to the widest so columns stay
    # aligned and the box banding (still a two-region jigsaw here) survives.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (0, 5),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (1,),
    }
    region_map = [[(1, 1), (2, 1)], [(1, 2), (2, 2)]]
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == (
        "┌───────┬───────┐\n"
        "│ {0 5} │     2 │\n"
        "│       │       │\n"
        "│     3 │     1 │\n"
        "└───────┴───────┘"
    )


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
    assert all(1 <= value[0] <= size for value in result.witness.assignment.values())


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


# A connected tetromino partition of a 4x4 board — deliberately not the box
# tiling (which would be four 2x2 quadrants), so a found verdict proves the
# supplied jigsaw map drove the solve rather than a fallback.
JIGSAW_TETROMINOES = [
    0,
    0,
    0,
    1,
    0,
    1,
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
    # custom jigsaw region joining them catches the repeat (issue #123).
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
    # broke, a satisfiability fact, never a validator's judgment (#123
    # acceptance criteria).
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
    # symmetric to the over-sized pigeonhole case (#158 acceptance criteria).
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


def test_schrodinger_ordinary_broke_with_in_band_regions_carries_no_reason() -> None:
    # A contradiction unrelated to region sizing (two conflicting givens on
    # one cell) must not get blamed on a region that is well within the
    # cover band (#158 acceptance criteria: no false region-blame). Two
    # givens, not a given/placement pair: since #155 a placement refines to
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
    # S-cell-ness discovered from givens alone — none stated here — per #139's
    # story 4/5: k = len(values) - size S-cells per row, column, and box.
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
    # len(values) == size forces no S-cell at all — refused before classify
    # (#139 story 6), not silently accepted as a degenerate classic sudoku.
    puzzle = Puzzle(
        board=Board(size=9),  # default values 1-9, len == size
        constraints=(Constraint(type="schrodinger"),),
    )

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


def test_schrodinger_with_values_more_than_twice_size_is_broke() -> None:
    # Over 2*size digits can't fit even every cell doubled up — a genuine
    # infeasibility, not a special refusal (#139 story 7).
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
    # No-regression (#139 story 23): an ordinary puzzle's witness stays every
    # cell a 1-tuple, exactly as before the layer existed.
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
    # No-regression: an empty s_directives tuple is a no-op — the missing-layer
    # guard fires only when a pin is actually present, so an ordinary puzzle
    # verdicts exactly as before.
    puzzle = Puzzle(board=BOARD, givens=(Given(address="R1C1", digit=5),))

    result = verdict(puzzle, WorkingState(s_directives=()))

    assert result.kind == "found"


def test_verdict_runs_a_first_light_singleton_and_s_cell_pin_end_to_end() -> None:
    # The tracer's headline (issue #153): a puzzle stating just a singleton pin
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
    # #155's headline divergence: on a Schrödinger board a placement refines
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
    # #155's malformed AC: the digit-range refusal must survive the rewrite
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
    # Issue #155: a placement refines to d ∈ content on a Schrödinger board,
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
