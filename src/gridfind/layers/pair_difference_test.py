"""pair-difference behaviour, tested at two seams.

Mirrors `group_sum_test.py`: verdict-seam behaviour (a clue's effect on the
completion) plus the direct rule readback, the one claim a solve
cannot make on its own — that a clue emitted its *own* rule rather than being
satisfied by accident.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import MalformedPuzzleError, build_engine
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


@pytest.mark.parametrize("cell_count", [1, 3], ids=["too few", "too many"])
def test_a_pair_difference_clue_with_the_wrong_cell_count_raises_malformed(
    cell_count: int,
) -> None:
    # A pair relation names exactly two cells; a clue that doesn't must fail
    # loud with the malformed-input contract, not an opaque tuple-unpack
    # error out of the emitter.
    cells = [f"R1C{i + 1}" for i in range(cell_count)]
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="pair-difference", params={"cells": cells, "diff": 1}),
        ),
    )

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


def _negated_pair_difference(cells: tuple[str, str], diff: int) -> Constraint:
    return Constraint(
        type="pair-difference",
        params={"cells": list(cells), "diff": diff, "negate": True},
    )


def test_a_negated_pair_difference_forbids_that_exact_difference() -> None:
    # The negative-space mechanism's mode (sudokumaker.edge_clues): the pair
    # is pinned to the forbidden difference, so no completion exists.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_negated_pair_difference(("R1C1", "R1C2"), 3),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_negated_pair_difference_allows_every_other_difference() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_negated_pair_difference(("R1C1", "R1C2"), 3),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert abs(result.witness["R1C1"][0] - result.witness["R1C2"][0]) != 3


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
    assert result.witness["R1C2"][0] == 4
    assert abs(result.witness["R3C3"][0] - result.witness["R3C4"][0]) == 2


def test_pair_difference_reads_the_doubled_value_when_a_cell_is_the_modifier() -> None:
    # 9 is unreachable as |d0 - 1| for any digit 1-9 (max 8), but reachable
    # once R1C1 doubles: |2*5 - 1| == 9. Forcing R1C1 to be the modifier
    # isolates the claim — the relation only balances if it read R1C1's
    # folded value, not its raw digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _pair_difference(("R1C1", "R1C2"), 9)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C2") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.d0("R1C1")) == 5


def test_pair_difference_reads_the_combined_s_value_of_a_doubled_s_cell() -> None:
    # Mirrors group_sum_test's doubled-S-cell coverage: a cell marked both a
    # modifier and an S-cell is worth 2*s_value (ADR-0010). R1C1's digits
    # combine to 3 (1+2), doubled to 6; R1C2 is a plain 2, so the difference
    # the relation must read is 4 — only true if it reads the folded value.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
            _pair_difference(("R1C1", "R1C2"), 4),
        ),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    content = engine.contents("R1C1")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 1)
    engine.model.add(content[1] == 2)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 2)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
