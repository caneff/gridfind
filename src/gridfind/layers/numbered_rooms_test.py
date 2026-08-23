"""`numbered-rooms` behaviour, tested at two seams.

Mirrors `indexing_test.py`: the direct rule readback — that a clue emitted
its own `add_element` involution over the right line and target, not that a
solve happened to satisfy it — plus verdict-seam found/broke behaviour, and
the ADR-0009 digit-read exception (a doubler never shifts the index).
"""

from __future__ import annotations

from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import numbered_rooms_rules
from gridfind.layers.numbered_rooms import NumberedRooms
from gridfind.layers.outside_cells import OutsideCells
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=4)

# The line ordered from the clue inward: R1C2 (near) through R4C2 (far), with
# R0C2 the outside cell above column 2.
_LINE = ("R1C2", "R2C2", "R3C2", "R4C2")


def _numbered_rooms(cells: tuple[str, ...] = ("R0C2", *_LINE)) -> Constraint:
    """`cells[0]` the outside cell, `cells[1:]` its line ordered from the
    clue inward — the shape `frame.py`'s decode and this layer share."""
    return Constraint("numbered-rooms", params={"cells": list(cells)})


def test_numbered_rooms_emits_one_element_per_group() -> None:
    puzzle = Puzzle(board=BOARD, constraints=(_numbered_rooms(),))
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert numbered_rooms_rules(engine) == [("R0C2", "R1C2", list(_LINE))]


def test_no_numbered_rooms_constraint_emits_nothing() -> None:
    engine = build_engine([GridCells(), OutsideCells(), NumberedRooms()], board=BOARD)

    assert numbered_rooms_rules(engine) == []


def test_near_cell_names_its_own_position_resolves_found() -> None:
    # R1C2 = 1 (nearest the outside cell) names position 1 — itself. The
    # outside cell must then equal R1C2's own digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_numbered_rooms(),),
        givens=(
            Given(address="R1C2", digit=1),
            Given(address="R2C2", digit=3),
            Given(address="R3C2", digit=4),
            Given(address="R4C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R0C2"][0] == 1


def test_near_cell_names_a_farther_position_resolves_found() -> None:
    # R1C2 = 3 names position 3, R3C2 — given 4 — so the outside cell must
    # hold 4, not R1C2's own digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_numbered_rooms(),),
        givens=(
            Given(address="R1C2", digit=3),
            Given(address="R2C2", digit=1),
            Given(address="R3C2", digit=4),
            Given(address="R4C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R0C2"][0] == 4


def test_numbered_rooms_contradiction_resolves_broke() -> None:
    # R1C2 = 3 names position 3 (R3C2, given 4), but the outside cell is
    # given 2 — a mismatch the rule must refuse.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_numbered_rooms(),),
        givens=(
            Given(address="R0C2", digit=2),
            Given(address="R1C2", digit=3),
            Given(address="R2C2", digit=1),
            Given(address="R3C2", digit=4),
            Given(address="R4C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_numbered_rooms_reads_the_raw_digit_under_a_discovered_doubler() -> None:
    # R1C2 doubled to 3 folds to modifier_value 6 -- out of the line's 1..4
    # index range, so an index read through the folded value would be
    # infeasible. NumberedRooms reads d0 (ADR-0009's digit-read exception):
    # position 3 selects R3C2, and the outside cell tracks R3C2's own digit,
    # never influenced by the doubler.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _numbered_rooms()),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C2"] == 1)
    engine.model.add(engine.d0("R1C2") == 3)
    engine.model.add(engine.d0("R3C2") == 4)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.d0("R0C2")) == 4
