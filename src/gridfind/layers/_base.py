"""Helpers shared across layer modules.

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
layer file, because more than one layer needs them.
"""

from __future__ import annotations

from collections.abc import Callable

from ortools.sat.python import cp_model

from gridfind.engine import Engine


def grid_content(engine: Engine) -> list[list[list[cp_model.IntVar]]]:
    """The grid's cells as their raw content sequences, resolved at call time
    in phase 2. Named for *content*, the decided word, rather
    than for the CP-SAT variables it happens to return — "variable" is an
    implementation word kept out of the spoken vocabulary (CONTEXT.md).

    `board` stores the grid as cell *addresses*, not content, on purpose: a
    Schrödinger layer can widen a cell's content to length 2 in phase 1, so
    resolving an address to its content must wait until here. Hands back
    each cell's raw sequence, never a folded scalar — a
    width-1 cell's sequence has length 1, so a caller that wants one
    variable per cell folds it itself.
    """
    grid = engine.cell_geometry.grid
    return [[engine.contents(address) for address in row] for row in grid]


def emit_distinct_count(
    engine: Engine, cells: list[cp_model.IntVar], *, target: int, label: str
) -> None:
    """Rule: exactly `target` distinct values appear across `cells`, repeats
    allowed — a counting rule, unlike an AllDifferent. For each
    candidate digit, a reified "present" bool tracks whether any cell holds
    it; the digit count is the sum of those bools.

    That is **one** rule, emitted at a cost of O(cells x digits) solver
    constraints — over 160 for a 9-cell row, the price of the counting rule
    rather than a sign of many rules.
    """
    board = engine.board
    present_per_digit = []
    for digit in board.values:
        holds_digit = engine.reify_holds(cells, digit, label)
        present = engine.model.new_bool_var(f"{label}.present{digit}")
        engine.model.add_max_equality(present, holds_digit)
        present_per_digit.append(present)
    engine.model.add(sum(present_per_digit) == target)


def emit_house(
    engine: Engine, cells: list[list[cp_model.IntVar]], *, label: str
) -> None:
    """Rule: every digit in the board's domain occupies exactly one content
    slot across `cells` — `d0` always, `d1` too where it holds a real digit
    (an S-cell's second digit). No separate is_S gate is needed: a
    non-S-cell's `d1` sits on its own sentinel, always above every real
    digit, so it can never equal one.

    No-repeats and cover collapse into this one rule: a house of `len(cells)`
    cells offers `sum(len(content) for content in cells)` real-or-sentinel
    slots, and binding each of the board's digits to exactly one of them
    forces exactly `len(values) - len(cells)` cells to their second slot —
    the S-cell count per house EMERGES, nothing here states it.
    """
    slots = [slot for content in cells for slot in content]
    for digit in engine.board.values:
        holds_digit = engine.reify_holds(slots, digit, label)
        engine.model.add(sum(holds_digit) == 1)


def emit_over_pairs(
    engine: Engine,
    pairs: list[tuple[cp_model.IntVar, cp_model.IntVar]],
    rel: Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None],
) -> None:
    """Rule: `rel(engine, a, b)` holds for every pair in `pairs` — the shared
    walk behind every explicit-pair variant: `pair-difference` and
    `pair-ratio` (both via `PairRelation`, decision 5), and `thermo`'s
    consecutive-pair decomposition.

    A callback rather than a relation-as-data table: the relation a
    pair-difference or pair-ratio clue wants (an absolute difference, a
    ratio) is native CP-SAT — `add_abs_equality`, a reified either-or — so
    encoding it as an AllowedAssignments table would trade a direct
    primitive for indirection with nothing gained (ADR-0001 keeps the engine
    seam raw OR-Tools). `rel` closes over whatever per-clue data it needs (a
    target difference, a target ratio); this helper never learns clue or
    path structure, so a future path-shaped variant can decompose its own
    path into consecutive pairs before calling it.
    """
    for a, b in pairs:
        rel(engine, a, b)
