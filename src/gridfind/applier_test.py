"""The working-state applier's modifier-directive path: a declared modifier
cell (a doubler read off a link's red bit) pins `is_modifier` on the built
model, and a directive with no modifier layer to honor it is malformed —
mirroring the Schrödinger-directive rules `apply` already enforces."""

import pytest
from ortools.sat.python import cp_model

from gridfind.applier import apply
from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.doubler import Doubler
from gridfind.puzzle import Board, ModifierDirective, Puzzle, WorkingState


def test_modifier_directive_without_a_modifier_layer_is_malformed() -> None:
    engine = build_engine([GridCells()], board=Board(size=4))
    state = WorkingState(
        modifier_directives=(ModifierDirective("R1C1", is_modifier=True),)
    )

    with pytest.raises(MalformedPuzzleError, match="modifier"):
        apply(engine, Puzzle(board=Board(size=4)), state)


def test_declared_modifiers_are_pinned_so_three_in_one_row_is_infeasible() -> None:
    # The directives are honored, not ignored: three declared doublers in one
    # row violate the modifier layer's one-per-house rule, so the model is
    # infeasible. Were the directives dropped, the solver would freely place a
    # single modifier per house and the model would solve.
    engine = build_engine([GridCells(), Doubler()], board=Board(size=4))
    state = WorkingState(
        modifier_directives=(
            ModifierDirective("R1C1", is_modifier=True),
            ModifierDirective("R1C2", is_modifier=True),
            ModifierDirective("R1C3", is_modifier=True),
        )
    )

    apply(engine, Puzzle(board=Board(size=4)), state)

    status = cp_model.CpSolver().solve(engine.model)
    assert status == cp_model.INFEASIBLE
