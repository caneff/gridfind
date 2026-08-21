import pytest

from gridfind.engine import build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import cell_values
from gridfind.layers.outside_cells import OutsideCells
from gridfind.puzzle import Board, Constraint


def test_outside_cells_creates_an_off_grid_address_a_clues_cells_param_names() -> None:
    # A border address (row 0 is off a 4x4's 1..4 grid) referenced by an
    # ordinary pair-relation clue becomes a real cell — the machinery a
    # decoration on an outside cell needs to bind.
    constraint = Constraint(
        "pair-difference", params={"cells": ["R0C1", "R1C1"], "diff": 1}
    )
    engine = build_engine(
        [GridCells(), OutsideCells()], (constraint,), board=Board(size=4)
    )

    assert "R0C1" in engine.cells
    assert len(engine.cells["R0C1"].content) == 1


def test_outside_cell_is_bounded_to_the_boards_own_values() -> None:
    constraint = Constraint(
        "pair-difference", params={"cells": ["R0C1", "R1C1"], "diff": 1}
    )
    engine = build_engine(
        [GridCells(), OutsideCells()], (constraint,), board=Board(size=4)
    )

    assert cell_values(engine, "R0C1") == [1, 2, 3, 4]


def test_outside_cells_never_creates_a_cell_the_grid_already_covers() -> None:
    # An ordinary inner-only clue leaves the cell count at exactly the grid's
    # own — no cell is invented for an address already on the board.
    constraint = Constraint(
        "pair-difference", params={"cells": ["R1C1", "R1C2"], "diff": 1}
    )
    engine = build_engine(
        [GridCells(), OutsideCells()], (constraint,), board=Board(size=4)
    )

    assert len(engine.cells) == 4 * 4


def test_two_constraints_naming_the_same_outside_cell_share_one_cell() -> None:
    # The single-creator machinery: two clues referencing R0C1 must not
    # register it twice — a second add_cell would silently orphan whatever
    # rule the first clue's layer already captured against the first
    # variable.
    a = Constraint("pair-difference", params={"cells": ["R0C1", "R1C1"], "diff": 1})
    b = Constraint("pair-ratio", params={"cells": ["R0C1", "R0C2"], "k": 2})
    engine = build_engine([GridCells(), OutsideCells()], (a, b), board=Board(size=4))

    # The grid's own 16 cells, plus exactly R0C1 and R0C2 — R0C1 named twice
    # (once by each clue) still costs one cell, not two.
    assert len(engine.cells) == 4 * 4 + 2


def test_a_corner_never_referenced_by_any_clue_is_never_created() -> None:
    constraint = Constraint(
        "pair-difference", params={"cells": ["R0C1", "R1C1"], "diff": 1}
    )
    engine = build_engine(
        [GridCells(), OutsideCells()], (constraint,), board=Board(size=4)
    )

    assert "R0C0" not in engine.cells


@pytest.mark.parametrize(
    "constraint",
    [
        Constraint("rows-distinct"),
        Constraint("regions-distinct", params={"regions": [0, 1, 1, 0]}),
    ],
    ids=["no-cells-param", "cells-shaped-differently"],
)
def test_outside_cells_tolerates_a_constraint_with_no_cells_address_list(
    constraint: Constraint,
) -> None:
    engine = build_engine(
        [GridCells(), OutsideCells()], (constraint,), board=Board(size=4)
    )

    assert len(engine.cells) == 4 * 4
