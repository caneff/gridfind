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
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board


def _is_modifier(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])


def _is_s(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])


def _modifier_value(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["modifier_value"])


def _engine(size: int = 4) -> Engine:
    return build_engine([GridCells(), Doubler()], board=Board(size=size))


def test_registers_modifier_type_per_cell_not_one_global_name() -> None:
    # The witness source is per-cell: every cell the layer governs maps to its
    # own declared name, keyed by address rather than one puzzle-wide value.
    engine = _engine()
    types = engine.modifier_types()
    assert types == dict.fromkeys(engine.cells, "doubler")


def test_doubler_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([Doubler()], board=Board(size=4))


def test_composes_modifier_placement_one_per_house() -> None:
    engine = _engine()
    is_modifier = _is_modifier(engine)
    solver = cp_model.CpSolver()

    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    grid = engine.cell_geometry.grid
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


def test_doubler_folds_the_s_value_beneath_a_doubled_s_cell() -> None:
    # A cell marked both a modifier and an S-cell is worth 2·s_value: the
    # doubler doubles the value beneath it — the S-cell's combined digits — not
    # the raw digit (ADR-0010). d0=1, d1=2 sum to s_value 3, so modifier_value
    # folds to 6. OPTIMAL proves the combination is feasible (no rule forbids a
    # cell holding both marks).
    engine = build_engine(
        [GridCells(), Schrodinger(), Doubler()], board=Board(size=4, values=range(5))
    )
    is_modifier = _is_modifier(engine)
    is_s = _is_s(engine)
    content = engine.contents("R1C1")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 1)
    engine.model.add(content[1] == 2)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status == cp_model.OPTIMAL
    assert solver.value(_modifier_value(engine)["R1C1"]) == 6


def test_forcing_two_modifiers_into_one_row_is_still_infeasible() -> None:
    # Regression: Doubler must not weaken ModifierPlacement's own rules.
    engine = _engine()
    is_modifier = _is_modifier(engine)
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_modifier["R1C2"] == 1)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
