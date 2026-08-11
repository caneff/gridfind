"""The `doubler` layer: the concrete `{type: doubler}` modifier. Composes
`ModifierPlacement` unchanged — these
tests pin `is_modifier` and read digits directly, exactly the way
`modifier_test.py` does, plus the one thing doubler adds: the model-level
`"modifier_value"` fold (`2·d0` when discovered, `d0` otherwise).
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.distinct import cols, regions, rows
from gridfind.layers.doubler import Doubler
from gridfind.puzzle import Board


def _is_modifier(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])


def _modifier_value(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["modifier_value"])


def _engine(size: int = 4) -> Engine:
    return build_engine([GridCells(), Doubler()], board=Board(size=size))


def test_doubler_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([Doubler()], board=Board(size=4))


def test_composes_modifier_placement_one_per_house() -> None:
    engine = _engine()
    is_modifier = _is_modifier(engine)
    solver = cp_model.CpSolver()

    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    grid = cast("list[list[str]]", engine.structures["grid"])
    for partition in (rows, cols, regions):
        for group in partition(grid):
            addresses = list(group)
            assert sum(solver.value(is_modifier[a]) for a in addresses) == 1


@pytest.mark.parametrize(
    ("discovered", "factor"),
    [(0, 1), (1, 2)],
    ids=["not-discovered", "discovered"],
)
def test_modifier_value_folds_the_digit(discovered: int, factor: int) -> None:
    engine = _engine()
    is_modifier = _is_modifier(engine)
    modifier_value = _modifier_value(engine)
    engine.model.add(is_modifier["R1C1"] == discovered)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    folded = solver.value(modifier_value["R1C1"])
    assert folded == factor * solver.value(engine.d0("R1C1"))


def test_forcing_two_modifiers_into_one_row_is_still_infeasible() -> None:
    # Regression: Doubler must not weaken ModifierPlacement's own rules.
    engine = _engine()
    is_modifier = _is_modifier(engine)
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_modifier["R1C2"] == 1)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
