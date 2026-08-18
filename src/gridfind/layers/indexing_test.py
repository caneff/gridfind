"""`indexing` behaviour, tested at two seams.

Mirrors `thermo_test.py`: the direct rule readback — that a clue emitted its
own `add_element` involution over the right line and coordinate, not that a
solve happened to satisfy it — plus verdict-seam found/broke behaviour for
both axes, and the ADR-0009 digit-read exception (a doubler never shifts the
index).

The width-1 tests above exercise a bare stack (no widening layer), where
`Indexing` takes its `add_element` fast path. The S-cell tests below stack
`schrodinger` alongside `indexing` and drive the `verdict()` seam directly
(`SCellPin`/`SingletonPin` s_directives, `S_BOARD`'s `0..N` domain, mirroring
`verdict_test.py`'s own S-cell fixtures) — membership over a widened cell's
two slots and the index-0 refusal both only have a defined meaning once a
widening layer is in the stack.
"""

from __future__ import annotations

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import indexing_rules
from gridfind.layers.indexing import Indexing
from gridfind.puzzle import Board, Constraint, Given, Puzzle, WorkingState
from gridfind.s_directives import SCellPin, SDirective, SingletonPin
from gridfind.verdict import verdict

BOARD = Board(size=4)

# A Schrödinger board small enough to solve fast: 5 digits (0-4) over a
# 4-wide line, the classic `0..N` domain (ADR-0014) an indexing control's
# index-0 refusal needs to be reachable at all.
S_BOARD = Board(size=4, values=range(5))


def _indexing(axis: str, cells: tuple[str, ...]) -> Constraint:
    return Constraint("indexing", params={"axis": axis, "cells": list(cells)})


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        (
            (_indexing("col", ("R1C2",)),),
            [("R1C2", 2, ["R1C1", "R1C2", "R1C3", "R1C4"])],
        ),
        (
            (_indexing("row", ("R2C1",)),),
            [("R2C1", 2, ["R1C1", "R2C1", "R3C1", "R4C1"])],
        ),
        (
            (_indexing("col", ("R1C2", "R3C4")),),
            [
                ("R1C2", 2, ["R1C1", "R1C2", "R1C3", "R1C4"]),
                ("R3C4", 4, ["R3C1", "R3C2", "R3C3", "R3C4"]),
            ],
        ),
        (
            (_indexing("col", ("R1C2",)), _indexing("row", ("R2C1",))),
            [
                ("R1C2", 2, ["R1C1", "R1C2", "R1C3", "R1C4"]),
                ("R2C1", 2, ["R1C1", "R2C1", "R3C1", "R4C1"]),
            ],
        ),
    ],
    ids=[
        "column-indexing reads across its own row",
        "row-indexing reads down its own column",
        "two marked cells in one clue",
        "a column clue and a row clue together",
    ],
)
def test_indexing_emits_one_element_per_marked_cell(
    constraints: tuple[Constraint, ...],
    expected: list[tuple[str, int, list[str]]],
) -> None:
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert indexing_rules(engine) == expected


def test_no_indexing_constraint_emits_nothing() -> None:
    engine = build_engine([GridCells(), Indexing()], board=BOARD)

    assert indexing_rules(engine) == []


def test_column_indexing_self_reference_resolves_found() -> None:
    # R1C2 = 2: the control names its own position, so (R1, 2) = 2 is
    # trivially the control cell itself.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_indexing("col", ("R1C2",)),),
        givens=(Given(address="R1C2", digit=2),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 2


def test_column_indexing_contradiction_resolves_broke() -> None:
    # R1C2 = 3 demands (R1, 3) = R1C3 hold C = 2, but R1C3 is given 4.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_indexing("col", ("R1C2",)),),
        givens=(Given(address="R1C2", digit=3), Given(address="R1C3", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_column_indexing_contradiction_flips_found_with_the_clue_stripped() -> None:
    # Strip-and-recheck: the same givens alone (no indexing constraint) are
    # satisfiable, so the broke fixture above proves the clue, not the givens.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(),
        givens=(Given(address="R1C2", digit=3), Given(address="R1C3", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_row_indexing_self_reference_resolves_found() -> None:
    # The transpose of the column case: R2C1 = 2 names itself.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_indexing("row", ("R2C1",)),),
        givens=(Given(address="R2C1", digit=2),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R2C1"][0] == 2


def test_row_indexing_contradiction_resolves_broke() -> None:
    # R2C1 = 3 demands (3, C1) = R3C1 hold R = 2, but R3C1 is given 4.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_indexing("row", ("R2C1",)),),
        givens=(Given(address="R2C1", digit=3), Given(address="R3C1", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_row_indexing_contradiction_flips_found_with_the_clue_stripped() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(),
        givens=(Given(address="R2C1", digit=3), Given(address="R3C1", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_indexing_reads_the_raw_digit_under_a_discovered_doubler() -> None:
    # R1C1 doubled to 3 folds to modifier_value 6 — out of a 4-wide board's
    # 0-based index range (0..3), so an index read through the folded value
    # would be infeasible. Indexing reads d0 (ADR-0009's digit-read
    # exception): position 3 selects R1C3, which must hold C = 1, the
    # control's own column — never influenced by the doubler.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _indexing("col", ("R1C1",))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    modifier_value = cast(
        "dict[str, cp_model.IntVar]", engine.structures["modifier_value"]
    )
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 3)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.d0("R1C3")) == 1
    assert solver.value(modifier_value["R1C1"]) == 6


def test_indexing_stacks_over_schrodinger_without_s_blind_refusal() -> None:
    # indexing declares no s_blind, so the compose-time refusal
    # (`build_stack`'s own `refuse_s_blind_over_widening` call) that rejects
    # e.g. thermo + schrodinger must leave indexing + schrodinger standing —
    # no `SBlindLayerError`, all the way through a built engine.
    puzzle = Puzzle(
        board=S_BOARD,
        constraints=(Constraint(type="schrodinger"), _indexing("col", ("R1C2",))),
    )

    canonical, layers = build_stack(puzzle.constraints, size=S_BOARD.size)
    build_engine(layers, tuple(canonical), board=S_BOARD)


@pytest.mark.parametrize(
    ("marked_cells", "s_directives", "givens"),
    [
        pytest.param(
            ("R1C2",),
            (SCellPin(address="R1C2", pair=frozenset({1, 3})),),
            (Given(address="R1C1", digit=2), Given(address="R1C3", digit=2)),
            id="s-cell control indexes from both digits",
        ),
        pytest.param(
            ("R1C4",),
            (
                SingletonPin(address="R1C4", digit=1),
                SCellPin(address="R1C1", pair=frozenset({1, 4})),
            ),
            (),
            id="s-cell indexed cell matched by its second digit",
        ),
    ],
)
def test_s_cell_indexing_membership_resolves_found(
    marked_cells: tuple[str, ...],
    s_directives: tuple[SDirective, ...],
    givens: tuple[Given, ...],
) -> None:
    puzzle = Puzzle(
        board=S_BOARD,
        constraints=(Constraint(type="schrodinger"), _indexing("col", marked_cells)),
        givens=givens,
    )
    state = WorkingState(s_directives=s_directives)

    result = verdict(puzzle, state)

    assert result.kind == "found"


_R1C4_INDEXES_1_INTO_R1C1 = (SingletonPin(address="R1C4", digit=1),)


def test_s_cell_second_digit_target_contradiction_resolves_broke() -> None:
    # R1C4 = 1 demands (R1,1)=R1C1 hold C=4, R1C4's own column. R1C1 is an
    # S-cell pinned {1, 2} — neither digit is 4, so the demand on its second
    # (and first) slot fails: the found parametrized case above pins R1C1 to
    # {1, 4} instead, so this is that same shape with the match removed.
    puzzle = Puzzle(
        board=S_BOARD,
        constraints=(Constraint(type="schrodinger"), _indexing("col", ("R1C4",))),
    )
    state = WorkingState(
        s_directives=(
            *_R1C4_INDEXES_1_INTO_R1C1,
            SCellPin(address="R1C1", pair=frozenset({1, 2})),
        )
    )

    result = verdict(puzzle, state)

    assert result.kind == "broke"


def test_s_cell_second_digit_target_contradiction_flips_found_when_stripped() -> None:
    puzzle = Puzzle(board=S_BOARD, constraints=(Constraint(type="schrodinger"),))
    state = WorkingState(
        s_directives=(
            *_R1C4_INDEXES_1_INTO_R1C1,
            SCellPin(address="R1C1", pair=frozenset({1, 2})),
        )
    )

    result = verdict(puzzle, state)

    assert result.kind == "found"


_R1C2_HOLDS_1_AND_3 = (SCellPin(address="R1C2", pair=frozenset({1, 3})),)


def test_s_cell_control_second_digit_contradiction_resolves_broke() -> None:
    # R1C2 is an S-cell holding {1, 3}: its second digit (3) demands
    # (R1,3)=R1C3 hold C=2 (R1C2's own column), but R1C3 is separately
    # given 4 — a contradiction on the S-cell's second index alone.
    puzzle = Puzzle(
        board=S_BOARD,
        constraints=(Constraint(type="schrodinger"), _indexing("col", ("R1C2",))),
        givens=(Given(address="R1C1", digit=2), Given(address="R1C3", digit=4)),
    )
    state = WorkingState(s_directives=_R1C2_HOLDS_1_AND_3)

    result = verdict(puzzle, state)

    assert result.kind == "broke"


def test_s_cell_control_second_digit_contradiction_flips_found_when_stripped() -> None:
    # Strip-and-recheck: the same givens and S-cell pin alone (no indexing
    # constraint) are satisfiable, so the broke fixture above proves the
    # clue, not the givens or the pin.
    puzzle = Puzzle(
        board=S_BOARD,
        constraints=(Constraint(type="schrodinger"),),
        givens=(Given(address="R1C1", digit=2), Given(address="R1C3", digit=4)),
    )
    state = WorkingState(s_directives=_R1C2_HOLDS_1_AND_3)

    result = verdict(puzzle, state)

    assert result.kind == "found"


def test_indexing_control_forced_to_zero_resolves_broke() -> None:
    # 0 names no position: a control forced to it has no digit >= 1 to index
    # from, so the layer's explicit refusal makes the state broke rather
    # than silently satisfied.
    puzzle = Puzzle(
        board=S_BOARD,
        constraints=(Constraint(type="schrodinger"), _indexing("col", ("R1C2",))),
    )
    state = WorkingState(s_directives=(SingletonPin(address="R1C2", digit=0),))

    result = verdict(puzzle, state)

    assert result.kind == "broke"


def test_indexing_control_forced_to_zero_flips_found_with_the_clue_stripped() -> None:
    puzzle = Puzzle(board=S_BOARD, constraints=(Constraint(type="schrodinger"),))
    state = WorkingState(s_directives=(SingletonPin(address="R1C2", digit=0),))

    result = verdict(puzzle, state)

    assert result.kind == "found"
