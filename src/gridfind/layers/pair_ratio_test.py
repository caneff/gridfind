"""pair-ratio behaviour (black kropki), tested at the
same two seams as `pair_difference_test.py`: verdict-seam behaviour (a clue's
effect on the completion) plus the direct rule readback — the one claim a
solve cannot make on its own, that a clue emitted its *own* reified either-or
rather than being satisfied by accident.
"""

import pytest

from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.conftest import pair_ratio_rules
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _pair_ratio(cells: tuple[str, str], k: int) -> Constraint:
    return Constraint(type="pair-ratio", params={"cells": list(cells), "k": k})


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        ((_pair_ratio(("R1C1", "R1C2"), 2),), [(["R1C1", "R1C2"], 2)]),
        (
            (
                _pair_ratio(("R1C1", "R1C2"), 2),
                _pair_ratio(("R3C3", "R3C4"), 3),
            ),
            [(["R1C1", "R1C2"], 2), (["R3C3", "R3C4"], 3)],
        ),
    ],
    ids=["one clue", "two clues"],
)
def test_pair_ratio_emits_one_rule_per_clue(
    constraints: tuple[Constraint, ...],
    expected: list[tuple[list[str], int]],
) -> None:
    """One stateless layer, one rule per clue."""
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert pair_ratio_rules(engine) == expected


def test_a_satisfiable_pair_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_ratio(("R1C1", "R1C2"), 2),),
        givens=(Given(address="R1C1", digit=2),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, b = result.witness["R1C1"][0], result.witness["R1C2"][0]
    assert a == 2 * b or b == 2 * a


def test_a_pair_that_cannot_meet_its_ratio_resolves_broke() -> None:
    # Both cells pinned to 5 — neither can be twice the other.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_ratio(("R1C1", "R1C2"), 2),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_labelled_non_two_ratio_is_honored_at_its_value() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_ratio(("R1C1", "R1C2"), 3),),
        givens=(Given(address="R1C1", digit=9),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, b = result.witness["R1C1"][0], result.witness["R1C2"][0]
    assert a == 3 * b or b == 3 * a


def test_two_clues_each_constrain_their_own_pair_independently() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _pair_ratio(("R1C1", "R1C2"), 2),
            _pair_ratio(("R3C3", "R3C4"), 3),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a1, b1 = result.witness["R1C1"][0], result.witness["R1C2"][0]
    a2, b2 = result.witness["R3C3"][0], result.witness["R3C4"][0]
    assert a1 == 2 * b1 or b1 == 2 * a1
    assert a2 == 3 * b2 or b2 == 3 * a2


def test_the_relation_is_undirected_either_cell_may_hold_the_larger_value() -> None:
    # The lower-addressed cell is pinned to the smaller digit — a directed
    # `a == k*b` would refuse this; the undirected relation must not.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_ratio(("R1C1", "R1C2"), 4),),
        givens=(Given(address="R1C1", digit=2),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 8


def test_a_ratio_of_one_forces_equality_and_breaks_under_distinctness() -> None:
    # k == 1 forces a == b, stated with no special-casing; a pair sharing a
    # row-distinct house then has no completion.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint("rows-distinct"),
            _pair_ratio(("R1C1", "R1C2"), 1),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


@pytest.mark.parametrize("cell_count", [1, 3], ids=["too few", "too many"])
def test_a_pair_ratio_clue_with_the_wrong_cell_count_raises_malformed(
    cell_count: int,
) -> None:
    cells = [f"R1C{i + 1}" for i in range(cell_count)]
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="pair-ratio", params={"cells": cells, "k": 2}),),
    )

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


def test_a_puzzle_mixing_pair_ratio_and_pair_difference_resolves_correctly() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(
                type="pair-difference", params={"cells": ["R1C1", "R1C2"], "diff": 5}
            ),
            _pair_ratio(("R3C3", "R3C4"), 2),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert abs(result.witness["R1C1"][0] - result.witness["R1C2"][0]) == 5
    a, b = result.witness["R3C3"][0], result.witness["R3C4"][0]
    assert a == 2 * b or b == 2 * a
