"""`clone` behaviour, tested at the seam the issue names: `verdict` for the
plain found/broke pair. The two cloned cells are non-attacking (different row,
column, and box), so the only rule relating them is the clone — a divergent
pair is `broke` because of the clone, not because a house forbids the repeat.
"""

from __future__ import annotations

from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.clone import Clone
from gridfind.layers.doubler import Doubler
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)
# R1C1 and R4C4 share no row, column, or box.
_PAIR = ("R1C1", "R4C4")


def _clone(cells: tuple[str, ...]) -> Constraint:
    return Constraint("clone", params={"cells": list(cells)})


def test_no_clone_constraint_emits_nothing() -> None:
    bare = build_engine([GridCells()], board=BOARD)
    with_layer = build_engine([GridCells(), Clone()], board=BOARD)

    assert len(with_layer.model.proto.constraints) == len(bare.model.proto.constraints)


def test_a_satisfiable_clone_resolves_found_with_a_witness() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_clone(_PAIR),),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    # The clone copies the digit onto its free partner.
    assert result.witness["R4C4"][0] == 1


def test_cloned_cells_with_divergent_digits_resolve_broke() -> None:
    # Both cells given, different digits — the clone requires equal digits, so
    # no assignment satisfies it. The cells are non-attacking, so the clone is
    # the sole cause of the break.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_clone(_PAIR),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R4C4", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def _structure(engine: Engine, name: str) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures[name])


def test_clone_copies_the_digit_not_the_modifier_value() -> None:
    # R1C1 is a doubler (worth 2·d0); cloned to the non-attacking plain R3C3.
    # The clone copies the digit — R3C3 holds R1C1's d0 — never the doubler
    # marking, so R1C1 is worth 2·3 while R3C3 stays worth its plain 3.
    engine = build_engine(
        [GridCells(), Doubler(), Clone()],
        constraints=(Constraint("clone", params={"cells": list(_PAIR)}),),
        board=BOARD,
    )
    is_modifier = _structure(engine, "is_modifier")
    modifier_value = _structure(engine, "modifier_value")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_modifier["R4C4"] == 0)
    engine.model.add(engine.d0("R1C1") == 3)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.d0("R4C4")) == 3
    assert solver.value(modifier_value["R1C1"]) == 6
    assert solver.value(modifier_value["R4C4"]) == 3
