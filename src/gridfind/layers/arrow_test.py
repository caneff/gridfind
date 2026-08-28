"""`arrow` behaviour: one bulb, one or more shafts, each independently
summing (by cell value) to the bulb.

Most of it is tested at the `verdict` seam — a satisfiable shaft resolves
found, an unsatisfiable one broke, and two shafts on one bulb must each hold
on their own. The doubler pair reads the shaft cell's folded `value_expr`
directly at the engine seam, the same channel `group-sum`/`double-arrow`
already prove (`value_expr`'s modifier composition is not this layer's own
code to get wrong a second way). The raise cases (empty bulb, a pill bulb,
no shafts, a zero-cell shaft) are proven through `verdict` on an in-memory
puzzle, mirroring `equality-cage`'s own odd-cell-count raise test.
"""

from __future__ import annotations

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _arrow(bulb: str, *shafts: tuple[str, ...]) -> Constraint:
    return Constraint(
        type="arrow",
        params={"bulb": [bulb], "arrows": [list(shaft) for shaft in shafts]},
    )


def test_a_satisfiable_arrow_resolves_found() -> None:
    # Bulb given 5; the shaft's other cell is left to the solver, satisfied
    # only by 2 (3 + 2 = 5).
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_arrow("R1C1", ("R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C3"][0] == 2


def test_a_shaft_summing_unequal_to_the_bulb_resolves_broke() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_arrow("R1C1", ("R1C2", "R1C3")),),
        givens=(
            Given(address="R1C1", digit=5),
            Given(address="R1C2", digit=3),
            Given(address="R1C3", digit=3),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_shafts_on_one_bulb_each_equal_the_bulb_independently() -> None:
    # Bulb given 5. The first shaft (R1C2) is pinned to 5, satisfying it on
    # its own; the second shaft (R2C1, R2C2) is pinned to 3 + 1 = 4, unequal
    # to the bulb — the whole clue must still break, since a shaft that
    # already holds does not excuse a sibling shaft that doesn't.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_arrow("R1C1", ("R1C2",), ("R2C1", "R2C2")),),
        givens=(
            Given(address="R1C1", digit=5),
            Given(address="R1C2", digit=5),
            Given(address="R2C1", digit=3),
            Given(address="R2C2", digit=1),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_shafts_on_one_bulb_both_holding_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_arrow("R1C1", ("R1C2",), ("R2C1", "R2C2")),),
        givens=(
            Given(address="R1C1", digit=5),
            Given(address="R1C2", digit=5),
            Given(address="R2C1", digit=3),
            Given(address="R2C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_digits_may_repeat_along_a_shaft() -> None:
    # A bare arrow states no distinctness of its own: a two-cell shaft
    # summing to the bulb as a flat repeat (2 + 2 = 4) is satisfiable.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_arrow("R1C1", ("R1C2", "R1C3")),),
        givens=(
            Given(address="R1C1", digit=4),
            Given(address="R1C2", digit=2),
            Given(address="R1C3", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_arrow_reads_the_doubled_value_of_a_shaft_cell() -> None:
    # R1C2 (the shaft's only cell) is the modifier: raw digit 3 doubles to 6,
    # matching the bulb R1C1 pinned at 6. Feasible only if the arrow read the
    # shaft cell's folded value, not its raw digit (3 != 6).
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _arrow("R1C1", ("R1C2",))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C2"] == 1)
    engine.model.add(engine.d0("R1C1") == 6)
    engine.model.add(engine.d0("R1C2") == 3)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_arrow_falls_back_to_the_digit_when_the_shaft_cell_is_not_the_modifier() -> (
    None
):
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _arrow("R1C1", ("R1C2",))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C2"] == 0)
    engine.model.add(engine.d0("R1C1") == 6)
    engine.model.add(engine.d0("R1C2") == 3)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_an_empty_bulb_raises_malformed() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="arrow", params={"bulb": [], "arrows": [["R1C2"]]}),
        ),
    )

    with pytest.raises(MalformedPuzzleError, match="bulb"):
        verdict(puzzle)


def test_a_pill_bulb_of_more_than_one_cell_raises_malformed() -> None:
    # Multi-cell bulbs (pills) are #762's follow-up — refused loud here
    # rather than read as though the bulb's first cell were the whole bulb.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(
                type="arrow",
                params={"bulb": ["R1C1", "R1C2"], "arrows": [["R1C3"]]},
            ),
        ),
    )

    with pytest.raises(MalformedPuzzleError, match="pill"):
        verdict(puzzle)


def test_no_shafts_raises_malformed() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="arrow", params={"bulb": ["R1C1"], "arrows": []}),
        ),
    )

    with pytest.raises(MalformedPuzzleError, match="shaft"):
        verdict(puzzle)


def test_a_zero_cell_shaft_raises_malformed() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(
                type="arrow", params={"bulb": ["R1C1"], "arrows": [["R1C2"], []]}
            ),
        ),
    )

    with pytest.raises(MalformedPuzzleError, match="shaft"):
        verdict(puzzle)
