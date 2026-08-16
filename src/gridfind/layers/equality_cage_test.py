"""equality-cage behaviour, tested at the seams the issue names: `verdict`
(mirroring `cage_test.py`), the emit seam via solver FEASIBLE/INFEASIBLE with
pinned cells, and the value channel via `modifier_value`/`s_value` pinning.

An equality cage forces its cells to balance even against odd digits and low
against high digits (the digit-range midpoint splitting each half), all
digits distinct. This file proves this layer's own behaviour in isolation,
bare (no composed `cage`) — the same shape `rellik_cage_test.py` uses for its
own layer. The composition with `cage` (the real equality cage a setter
places) is proven at the `verdict` seam in `verdict_test.py`, mirroring
`_killer_cage`/`_rellik_cage`.
"""

from __future__ import annotations

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.equality_cage import EqualityCage
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _equality_cage(cells: tuple[str, ...]) -> Constraint:
    return Constraint(type="equality-cage", params={"cells": list(cells)})


def test_no_equality_cage_constraint_emits_nothing() -> None:
    bare = build_engine([GridCells()], board=BOARD)
    with_layer = build_engine([GridCells(), EqualityCage()], board=BOARD)

    assert len(with_layer.model.proto.constraints) == len(bare.model.proto.constraints)


def test_a_satisfiable_equality_cage_resolves_found_with_a_witness() -> None:
    cells = ("R1C1", "R1C2", "R1C3", "R1C4")
    puzzle = Puzzle(board=BOARD, constraints=(_equality_cage(cells),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    digits = [result.witness[address][0] for address in cells]
    assert sum(1 for d in digits if d % 2 == 0) == 2
    assert sum(1 for d in digits if d < 5) == 2
    assert sum(1 for d in digits if d > 5) == 2


def test_an_unsatisfiable_equality_cage_resolves_broke() -> None:
    # Three givens are all odd (1, 3, 9) — the fourth, free cell can supply
    # at most one more even digit, so the even count can never reach 2.
    cells = ("R1C1", "R1C2", "R1C3", "R1C4")
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_equality_cage(cells),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=3),
            Given(address="R1C3", digit=9),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_an_odd_cell_count_equality_cage_raises_malformed() -> None:
    puzzle = Puzzle(
        board=BOARD, constraints=(_equality_cage(("R1C1", "R1C2", "R1C3")),)
    )

    with pytest.raises(MalformedPuzzleError, match="even"):
        verdict(puzzle)


def test_the_middle_digit_is_excluded_emergently_with_no_explicit_domain_bar() -> None:
    # A 9-digit board's midpoint digit, 5, is neither low nor high. Pinning
    # one cell to it leaves the other three to supply all 4 low-or-high
    # slots the balance needs — one more than 3 cells can hold — so the cage
    # goes infeasible with no domain bar this layer ever states.
    engine = build_engine(
        [GridCells(), EqualityCage()],
        (_equality_cage(("R1C1", "R1C2", "R1C3", "R1C4")),),
        board=BOARD,
    )
    engine.model.add(engine.d0("R1C1") == 5)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_equality_cage_reads_the_doubled_value_not_the_raw_digit() -> None:
    # R1C1's raw digit is 3 (low, odd); doubled its value is 6 (high, even).
    # The other three cells are fixed so the balance holds only under the
    # doubled reading (high=2, even=2, low=2 across all four).
    cells = ("R1C1", "R1C2", "R1C3", "R1C4")
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _equality_cage(cells)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 3)
    for address in ("R1C2", "R1C3", "R1C4"):
        engine.model.add(is_modifier[address] == 0)
    engine.model.add(engine.d0("R1C2") == 1)
    engine.model.add(engine.d0("R1C3") == 2)
    engine.model.add(engine.d0("R1C4") == 9)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_equality_cage_permits_the_raw_digit_reading_when_only_doubled_balances() -> (
    None
):
    # Companion to the above: with no modifier discovered on R1C1, its value
    # stays its raw digit 3 (low, odd), so the same fixed assignment leaves
    # low=3/high=1/even=1 across the four cells — none of the three balances
    # hold, proving the earlier feasibility tracked the doubled value, not a
    # digit-blind read.
    cells = ("R1C1", "R1C2", "R1C3", "R1C4")
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _equality_cage(cells)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    for address in cells:
        engine.model.add(is_modifier[address] == 0)
    engine.model.add(engine.d0("R1C1") == 3)
    engine.model.add(engine.d0("R1C2") == 1)
    engine.model.add(engine.d0("R1C3") == 2)
    engine.model.add(engine.d0("R1C4") == 9)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_equality_cage_over_a_widened_cell_reads_its_s_value() -> None:
    # R1C1 is forced S with digits {1, 3}: under the default `sum` combine
    # its value is 4 (high, even) on this 5-digit board (values 1-5,
    # midpoint (5+1)/2 = 3 -> low {1,2}, high {4,5}, 3 excluded). Its raw d0
    # alone (1) would read low+odd instead, so the other three cells are
    # fixed so the balance holds only under the s_value reading.
    engine = build_engine(
        [GridCells(), Schrodinger(), EqualityCage()],
        (_equality_cage(("R1C1", "R1C2", "R1C3", "R1C4")),),
        board=Board(size=4, values=range(1, 6)),
    )
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 1)
    engine.model.add(r1c1[1] == 3)
    for address in ("R1C2", "R1C3", "R1C4"):
        engine.model.add(is_s[address] == 0)
    engine.model.add(engine.d0("R1C2") == 1)
    engine.model.add(engine.d0("R1C3") == 2)
    engine.model.add(engine.d0("R1C4") == 5)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
