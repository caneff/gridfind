"""Helpers shared across layer modules (spec #4).

Three levels meet in this file, told apart by how many of each there are. A
**constraint** is one typed statement in a puzzle; it emits many **rules**,
each one atomic relation over cell content; and one rule may cost many
**solver constraints** — the `engine.model.add_*` calls below. This module
bridges the bottom two: it is where a single rule expands into many solver
constraints, which is why `emit_distinct_count` exists rather than one
`add_all_different` call. *Solver constraint* names that level without naming
a vendor (CONTEXT.md, map #1 decision 13).

`grid_content` and `emit_distinct_count` are package-internal APIs imported by
`rows`, `cols`, `regions`, and `line_count`. They live here, not in any one
layer file, because more than one layer needs them (issue #17).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine


def grid_content(engine: Engine) -> list[list[cp_model.IntVar]]:
    """The grid's cells as their primary content, resolved at call time in
    phase 2 (issue #19). Named for *content*, the decided word, rather than
    for the CP-SAT variables it happens to return — "variable" is an
    implementation word kept out of the spoken vocabulary (CONTEXT.md).

    `board` stores the grid as cell *addresses*, not content, on purpose: a
    Schrödinger layer can widen a cell's content to length 2 in phase 1, so
    resolving an address to its content must wait until here. The one cast
    lives in this helper — `structures` stays generic so every layer shares
    one channel; only this consumer needs the concrete type.
    """
    grid = cast("list[list[str]]", engine.structures["grid"])
    return [[engine.content(address) for address in row] for row in grid]


def emit_distinct_count(
    engine: Engine, cells: list[cp_model.IntVar], *, target: int, label: str
) -> None:
    """Rule: exactly `target` distinct values appear across `cells`, repeats
    allowed — a counting rule, unlike an AllDifferent (issue #10). For each
    candidate digit, a reified "present" bool tracks whether any cell holds
    it; the digit count is the sum of those bools.

    That is **one** rule, emitted at a cost of O(cells x digits) solver
    constraints — over 160 for a 9-cell row, the price of the counting rule
    rather than a sign of many rules.
    """
    board = engine.board
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


def emit_over_pairs(
    engine: Engine,
    pairs: list[tuple[cp_model.IntVar, cp_model.IntVar]],
    rel: Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None],
) -> None:
    """Rule: `rel(engine, a, b)` holds for every pair in `pairs` — the shared
    walk behind every explicit-pair variant (pair-sum today, a second variant
    at #42 decision 5).

    A callback rather than a relation-as-data table: the relation a pair-sum
    or pair-difference clue wants (a sum, an absolute difference) is native
    CP-SAT — `add`, `add_abs_equality` — so encoding it as an
    AllowedAssignments table would trade a direct primitive for indirection
    with nothing gained (ADR-0001 keeps the engine seam raw OR-Tools). `rel`
    closes over whatever per-clue data it needs (a target sum, a target
    difference); this helper never learns clue or path structure, so a future
    path-shaped variant can decompose its own path into consecutive pairs
    before calling it.
    """
    for a, b in pairs:
        rel(engine, a, b)
