"""pair-difference behaviour, tested at two seams.

Mirrors `group_sum_test.py`: verdict-seam behaviour (a clue's effect on the
completion) plus the direct rule readback, the one claim a solve
cannot make on its own — that a clue emitted its *own* rule rather than being
satisfied by accident.
"""

import pytest

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.conftest import pair_difference_rules
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _pair_difference(cells: tuple[str, str], diff: int) -> Constraint:
    return Constraint(
        type="pair-difference", params={"cells": list(cells), "diff": diff}
    )


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        ((_pair_difference(("R1C1", "R1C2"), 3),), [(["R1C1", "R1C2"], 3)]),
        (
            (
                _pair_difference(("R1C1", "R1C2"), 3),
                _pair_difference(("R3C3", "R3C4"), 1),
            ),
            [(["R1C1", "R1C2"], 3), (["R3C3", "R3C4"], 1)],
        ),
    ],
    ids=["one clue", "two clues"],
)
def test_pair_difference_emits_one_rule_per_clue(
    constraints: tuple[Constraint, ...],
    expected: list[tuple[list[str], int]],
) -> None:
    """One stateless layer, one rule per clue."""
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert pair_difference_rules(engine) == expected


def test_a_satisfiable_pair_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_difference(("R1C1", "R1C2"), 3),),
        givens=(Given(address="R1C1", digit=5),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert abs(result.witness["R1C1"][0] - result.witness["R1C2"][0]) == 3


def test_a_pair_that_cannot_meet_its_difference_resolves_broke() -> None:
    # Both cells pinned to 1 (diff 0) — a pair-difference wanting 3 has no
    # completion.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_difference(("R1C1", "R1C2"), 3),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_clues_each_constrain_their_own_pair_independently() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _pair_difference(("R1C1", "R1C2"), 3),
            _pair_difference(("R3C3", "R3C4"), 5),
        ),
        givens=(Given(address="R1C1", digit=2), Given(address="R3C3", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert abs(result.witness["R1C1"][0] - result.witness["R1C2"][0]) == 3
    assert abs(result.witness["R3C3"][0] - result.witness["R3C4"][0]) == 5


def test_a_broken_second_clue_breaks_the_whole_puzzle() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _pair_difference(("R1C1", "R1C2"), 3),
            _pair_difference(("R3C3", "R3C4"), 5),
        ),
        givens=(Given(address="R3C3", digit=1), Given(address="R3C4", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_the_relation_is_absolute_either_cell_may_hold_the_larger_value() -> None:
    # The lower-addressed cell is pinned to the larger digit — a directed
    # `a - b == k` would refuse this; the absolute relation must not.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_difference(("R1C1", "R1C2"), 4),),
        givens=(Given(address="R1C1", digit=9),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 5


def test_a_puzzle_mixing_group_sum_and_pair_difference_resolves_correctly() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 5}),
            _pair_difference(("R3C3", "R3C4"), 2),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=6)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 4  # 1 + 4 == 5
    assert abs(result.witness["R3C3"][0] - result.witness["R3C4"][0]) == 2
