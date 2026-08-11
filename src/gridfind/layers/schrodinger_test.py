"""The `schrodinger` layer's own mechanics: the
widening, the malformed refusal, and the `is_s` structure `distinct.py`'s
is_S-gated counting rule reads.

`verdict_test.py` covers the end-to-end acceptance criteria (found with the
right S-cell count per house, malformed, over-packed broke, a non-schrodinger
puzzle unaffected);
these tests isolate the layer's own model — one house type at a time, is_s
pinned directly, since forcing a contradictory S-cell count needs a pin
gridfind has no setter-facing directive for yet.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import (
    Engine,
    MalformedPuzzleError,
    MissingDependencyError,
    build_engine,
)
from gridfind.layers.board import GridCells
from gridfind.layers.distinct import DistinctOverGroups, rows
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board


def _is_s(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])


def _s_value(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["s_value"])


def test_default_combine_sums_an_s_cells_two_digits() -> None:
    # With no `combine` declared, an S-cell's two digits add: {2, 3} is worth 5,
    # not 23 (ADR-0010 decision 5). `concat` stays a choosable rule, exercised
    # where a cage reads the value.
    engine = build_engine(
        [GridCells(), Schrodinger()], board=Board(size=4, values=range(5))
    )
    is_s = _is_s(engine)
    s_value = _s_value(engine)
    content = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 2)
    engine.model.add(content[1] == 3)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(s_value["R1C1"]) == 5


def test_schrodinger_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([Schrodinger()], board=Board(size=4, values=range(5)))


def test_schrodinger_widens_every_cell_to_a_length_two_content_sequence() -> None:
    engine = build_engine(
        [GridCells(), Schrodinger()], board=Board(size=4, values=range(5))
    )

    assert engine.cells  # a real grid, not an empty one
    assert all(len(cell.content) == 2 for cell in engine.cells.values())


def test_schrodinger_registers_an_is_s_bool_per_cell() -> None:
    engine = build_engine(
        [GridCells(), Schrodinger()], board=Board(size=4, values=range(5))
    )

    assert set(_is_s(engine)) == set(engine.cells)


def test_schrodinger_rejects_a_board_whose_values_equal_its_size() -> None:
    # len(values) == size forces no S-cell — a degenerate classic, refused
    # rather than silently accepted.
    with pytest.raises(MalformedPuzzleError, match="9"):
        build_engine([GridCells(), Schrodinger()], board=Board(size=9))


def test_schrodinger_rejects_a_board_whose_values_are_fewer_than_its_size() -> None:
    with pytest.raises(MalformedPuzzleError):
        build_engine(
            [GridCells(), Schrodinger()], board=Board(size=9, values=range(1, 9))
        )


def test_schrodinger_accepts_a_board_whose_values_exceed_its_size() -> None:
    engine = build_engine(
        [GridCells(), Schrodinger()], board=Board(size=9, values=range(10))
    )

    assert len(engine.cells) == 81


def _row_engine(size: int, values: range) -> Engine:
    return build_engine(
        [GridCells(), Schrodinger(), DistinctOverGroups("rows-distinct", rows)],
        board=Board(size=size, values=values),
    )


def test_a_row_alone_solves_with_exactly_the_forced_s_cell_count() -> None:
    # Domain 0-4 (5 digits) over a 4-cell row: k = 1 S-cell, discovered by
    # solving — nobody states the count (the prototype's own core claim).
    engine = _row_engine(4, range(5))
    is_s = _is_s(engine)
    solver = cp_model.CpSolver()

    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    for row in range(1, 5):
        addresses = [f"R{row}C{c}" for c in range(1, 5)]
        assert sum(solver.value(is_s[a]) for a in addresses) == 1


def test_forcing_two_s_cells_into_one_row_is_infeasible() -> None:
    # A row's own gated-count rule demands exactly one S-cell (5 digits, 4
    # cells) — pinning a second is a repeat, not a fit.
    engine = _row_engine(4, range(5))
    is_s = _is_s(engine)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(is_s["R1C2"] == 1)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_forcing_a_whole_row_of_singletons_breaks_cover() -> None:
    # Every cell pinned not-S leaves only 4 real slots for 5 digits — the
    # fifth has nowhere to go.
    engine = _row_engine(4, range(5))
    is_s = _is_s(engine)
    for col in range(1, 5):
        engine.model.add(is_s[f"R1C{col}"] == 0)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
