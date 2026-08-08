"""Helpers shared across layer modules (spec #4).

`grid_vars` and `emit_distinct_count` are package-internal APIs imported by
`rows`, `cols`, `regions`, and `line_count`. They live here, not in any one
layer file, because more than one layer needs them (issue #17).
"""

from __future__ import annotations

from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, GridfindError


def grid_vars(engine: Engine) -> list[list[cp_model.IntVar]]:
    """The grid's cells as their primary CP-SAT variables, resolved at call
    time in phase 2 (issue #19). `board` stores the grid as cell *names*, not
    variables, on purpose: a Schrödinger layer can widen a cell's content to
    length 2 in phase 1, so name-to-variable resolution must wait until here.
    The one cast lives in this helper — `structures` stays generic so every
    layer shares one channel; only this consumer needs the concrete type.
    """
    grid = cast("list[list[str]]", engine.structures["grid"])
    return [[engine.cells[name].content[0] for name in row] for row in grid]


def emit_distinct_count(
    engine: Engine, cells: list[cp_model.IntVar], *, target: int, label: str
) -> None:
    """Rule: exactly `target` distinct values appear across `cells`, repeats
    allowed — a counting rule, unlike an AllDifferent (issue #10). For each
    candidate digit, a reified "present" bool tracks whether any cell holds
    it; the digit count is the sum of those bools.
    """
    board = engine.board
    if board is None:
        msg = f"{label} requires build_engine(..., board=...)"
        raise GridfindError(msg)
    present_per_digit = []
    for digit in board.values:
        holds_digit = []
        for i, cell in enumerate(cells):
            indicator = engine.model.new_bool_var(f"{label}.holds{digit}.{i}")
            engine.model.add(cell == digit).only_enforce_if(indicator)
            engine.model.add(cell != digit).only_enforce_if(indicator.negated())
            holds_digit.append(indicator)
        present = engine.model.new_bool_var(f"{label}.present{digit}")
        engine.model.add_max_equality(present, holds_digit)
        present_per_digit.append(present)
    engine.model.add(sum(present_per_digit) == target)
