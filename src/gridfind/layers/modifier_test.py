"""The `modifier-placement` layer's own mechanics: the `is_modifier`
structure, one-per-house, and the distinct-digit transversal.

No fold lives here yet — a doubler or other concrete modifier type is a
future layer that reuses this placement and reads `is_modifier` back —
so these tests pin `is_modifier` and read digits directly the way
`schrodinger_test.py` pins `is_s`, since gridfind has no setter-facing
modifier directive yet.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.distinct import cols, regions, rows
from gridfind.layers.modifier import ModifierPlacement
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board


def _is_modifier(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])


def _engine(size: int = 4) -> Engine:
    return build_engine([GridCells(), ModifierPlacement()], board=Board(size=size))


def test_modifier_placement_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([ModifierPlacement()], board=Board(size=4))


def test_registers_an_is_modifier_bool_per_cell() -> None:
    engine = _engine()

    assert set(_is_modifier(engine)) == set(engine.cells)


def test_solves_with_exactly_one_modifier_per_row_col_and_box() -> None:
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


def test_modified_cells_hold_each_digit_exactly_once() -> None:
    engine = _engine()
    is_modifier = _is_modifier(engine)
    solver = cp_model.CpSolver()

    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    modifier_digits = [
        solver.value(engine.d0(address))
        for address in engine.cells
        if solver.value(is_modifier[address])
    ]
    assert sorted(modifier_digits) == sorted(engine.board.values)


def test_forcing_two_modifiers_into_one_row_is_infeasible() -> None:
    engine = _engine()
    is_modifier = _is_modifier(engine)
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_modifier["R1C2"] == 1)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_forcing_a_whole_row_of_non_modifiers_breaks_the_row_count() -> None:
    engine = _engine()
    is_modifier = _is_modifier(engine)
    for col in range(1, 5):
        engine.model.add(is_modifier[f"R1C{col}"] == 0)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_forcing_two_modifiers_onto_the_same_digit_is_infeasible() -> None:
    # R1C1 and R2C3 sit in different rows, columns, and boxes, so pinning
    # both as modifiers satisfies the one-per-house rule for each of those
    # houses — isolating the failure to the transversal's "each digit at
    # most once among the modifiers" count.
    engine = _engine()
    is_modifier = _is_modifier(engine)
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_modifier["R2C3"] == 1)
    engine.restrict("R1C1", [2])
    engine.restrict("R2C3", [2])

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def _is_s(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])


def test_two_doubled_s_cells_sharing_a_second_digit_is_infeasible() -> None:
    # A doubled S-cell holds two digits and doubles both, so both must enter
    # the "each digit doubled at most once" transversal. R1C1 and R2C3 sit in
    # different rows, columns, and boxes, so pinning both as S-cell modifiers
    # satisfies one-per-house — isolating the failure to the transversal. Both
    # carry 4 as their second digit (d0s 3 and 0 stay distinct), so digit 4 is
    # doubled twice and the board must break.
    engine = build_engine(
        [GridCells(), Schrodinger(), ModifierPlacement()],
        board=Board(size=4, values=range(5)),
    )
    is_modifier, is_s = _is_modifier(engine), _is_s(engine)
    for address, (d0, d1) in {"R1C1": (3, 4), "R2C3": (0, 4)}.items():
        engine.model.add(is_modifier[address] == 1)
        engine.model.add(is_s[address] == 1)
        engine.model.add(engine.contents(address)[0] == d0)
        engine.model.add(engine.contents(address)[1] == d1)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_a_doubled_s_cell_with_distinct_digits_stays_feasible() -> None:
    # The over-constraint guard for the two-slot transversal: one doubled
    # S-cell on {3,4} occupies two distinct slots, leaving {0,1,2} for the
    # three remaining plain-cell modifiers — no digit doubled twice, so the
    # tightened cap must still admit a solution.
    engine = build_engine(
        [GridCells(), Schrodinger(), ModifierPlacement()],
        board=Board(size=4, values=range(5)),
    )
    is_modifier, is_s = _is_modifier(engine), _is_s(engine)
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(engine.contents("R1C1")[0] == 3)
    engine.model.add(engine.contents("R1C1")[1] == 4)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_composes_with_schrodinger_and_stays_feasible() -> None:
    # Regression: an `== 1` per-digit transversal count is a
    # bijection with `board.values`, which only matches the one-per-house
    # modifier count (== board.size) when `len(values) == size`. schrodinger
    # always widens `values` past `size`, so that bijection made every
    # composed board unconditionally infeasible. `<= 1` (true all-different)
    # composes: the digit domain widening leaves room for modifiers to skip
    # digits instead of forcing more modifiers than houses ever place.
    engine = build_engine(
        [GridCells(), Schrodinger(), ModifierPlacement()],
        board=Board(size=4, values=range(5)),
    )

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
