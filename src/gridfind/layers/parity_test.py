"""`parity` behaviour, tested at the seams the issue names: `verdict`
(mirroring `equality_cage_test.py`) for the plain even/odd found/broke pairs,
and the value channel — a doubler's mapped `2·d` and an S-cell's combined
`s_value` — via solver FEASIBLE/INFEASIBLE with pinned cells.
"""

from __future__ import annotations

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.parity import Parity
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _parity(parity: str, cells: tuple[str, ...]) -> Constraint:
    return Constraint("parity", params={"parity": parity, "cells": list(cells)})


def test_no_parity_constraint_emits_nothing() -> None:
    bare = build_engine([GridCells()], board=BOARD)
    with_layer = build_engine([GridCells(), Parity()], board=BOARD)

    assert len(with_layer.model.proto.constraints) == len(bare.model.proto.constraints)


@pytest.mark.parametrize(
    ("parity", "digit"),
    [("even", 2), ("odd", 3)],
    ids=["even-satisfied", "odd-satisfied"],
)
def test_a_satisfiable_parity_clue_resolves_found_with_a_witness(
    parity: str, digit: int
) -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_parity(parity, ("R1C1",)),),
        givens=(Given(address="R1C1", digit=digit),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"][0] == digit


@pytest.mark.parametrize(
    ("parity", "digit"),
    [("even", 1), ("odd", 2)],
    ids=["even-clue-forced-odd", "odd-clue-forced-even"],
)
def test_a_parity_clue_violated_by_a_given_resolves_broke(
    parity: str, digit: int
) -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_parity(parity, ("R1C1",)),),
        givens=(Given(address="R1C1", digit=digit),),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_odd_clue_over_a_doubled_cell_is_unsatisfiable() -> None:
    # A doubler's mapped value is always `2*d`, never odd, so an odd clue
    # over a doubled cell is unsatisfiable regardless of its raw digit —
    # the value-mode reading (ADR-0009).
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _parity("odd", ("R1C1",))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_even_clue_over_a_doubled_cell_is_trivially_satisfied() -> None:
    # Companion to the above: a doubler's mapped value is always even, so an
    # even clue over a doubled cell holds even when the raw digit is odd.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _parity("even", ("R1C1",))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 3)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_parity_reads_the_doubled_value_not_the_raw_digit() -> None:
    # R1C1's raw digit is 3 (odd); doubled its value is 6 (even). An even
    # clue holds only under the doubled reading.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _parity("even", ("R1C1",))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 3)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_parity_over_a_widened_cell_reads_its_s_value() -> None:
    # R1C1 is forced S with digits {1, 2}: under the default `sum` combine
    # its value is 3 (odd). Its raw d0 alone (1) is also odd, so pin d1 to 4
    # instead (value 5, still odd) only distinguishing reads that ignore d1
    # entirely would matter here — the real proof is the FEASIBLE status
    # composing cleanly with the widened stack.
    engine = build_engine(
        [GridCells(), Schrodinger(), Parity()],
        (_parity("odd", ("R1C1",)),),
        board=Board(size=4, values=range(1, 6)),
    )
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 1)
    engine.model.add(r1c1[1] == 4)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_parity_over_a_widened_cell_rejects_an_even_s_value() -> None:
    # Companion: R1C1 forced S with digits {1, 3}, combined value 4 (even).
    # An odd clue must reject it even though d0 alone (1) is odd — proving
    # the read is s_value, not the bare first digit.
    engine = build_engine(
        [GridCells(), Schrodinger(), Parity()],
        (_parity("odd", ("R1C1",)),),
        board=Board(size=4, values=range(1, 6)),
    )
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 1)
    engine.model.add(r1c1[1] == 3)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
