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
`rows`, `cols`, `regions`, and `line_count`. `emit_distinct_group` is imported
by `distinct.DistinctOverGroups` (which every distinct rule — rows, cols,
regions, the diagonals, and windoku's extra regions — rides).
`emit_indexed_position_match` is imported by `indexing` and `numbered_rooms`,
the two clues whose control cell's own digit names a position on a line. They
live here, not in any one layer file, because more than one layer needs them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from ortools.sat.python import cp_model

from gridfind.engine import Engine, sole


def grid_content(engine: Engine) -> list[list[list[cp_model.IntVar]]]:
    """The grid's cells as their real-digit-slot sequences, resolved at call
    time in phase 2 through `Engine.real_digit_values` — the guard-dropping
    unwrap of `real_digit_slots`, since every caller (a counting rule or a plain
    AllDifferent) already tolerates a non-S-cell's sentinel second slot on its
    own (`real_digit_slots`'s docstring) and needs no `.only_enforce_if`.

    `board` stores the grid as cell *addresses*, not content, on purpose: a
    Schrödinger layer can widen a cell's content to length 2 in phase 1, so
    resolving an address to its content must wait until here. Hands back
    each cell's slot sequence, never a folded scalar — a
    width-1 cell's sequence has length 1, so a caller that wants one
    variable per cell folds it itself.
    """
    grid = engine.cell_geometry.grid
    return [[engine.real_digit_values(address) for address in row] for row in grid]


def emit_distinct_count(
    engine: Engine, slots: list[cp_model.IntVar], *, target: int, label: str
) -> None:
    """Rule: exactly `target` distinct values appear across `slots`, repeats
    allowed — a counting rule, unlike an AllDifferent. For each
    candidate digit, a reified "present" bool tracks whether any slot holds
    it; the digit count is the sum of those bools. An S-cell contributes two
    slots, so both its digits count.

    That is **one** rule, emitted at a cost of O(slots x digits) solver
    constraints — over 160 for a 9-cell row, the price of the counting rule
    rather than a sign of many rules.
    """
    board = engine.board
    present_per_digit = []
    for digit in board.values:
        holds_digit = engine.reify_holds(slots, digit, label)
        present = engine.model.new_bool_var(f"{label}.present{digit}")
        engine.model.add_max_equality(present, holds_digit)
        present_per_digit.append(present)
    engine.model.add(sum(present_per_digit) == target)


def flatten_slots(
    cells: Iterable[Iterable[cp_model.IntVar]],
) -> list[cp_model.IntVar]:
    """A house's per-cell content lists as one flat slot list — `d0` always,
    `d1` too where a cell is an S-cell. `cells` already comes from
    `grid_content`, so no separate is_S gate is needed here: `real_digit_slots`
    is the one place that explains why a non-S-cell's `d1` drops out of a
    digit-presence reification on its own. The single home for this walk:
    `emit_house` and `line-count-distinct` both read a house's slots this way.
    """
    return [slot for content in cells for slot in content]


def emit_house(
    engine: Engine, cells: list[list[cp_model.IntVar]], *, label: str
) -> None:
    """Rule: every digit in the board's domain occupies exactly one content
    slot across `cells` — `d0` always, `d1` too where it holds a real digit
    (an S-cell's second digit). No separate is_S gate is needed: `cells`
    already came through `grid_content`'s `real_digit_values` read, whose
    `real_digit_slots` base is the one place the sentinel invariant lives.

    No-repeats and cover collapse into this one rule: a house of `len(cells)`
    cells offers `sum(len(content) for content in cells)` real-or-sentinel
    slots, and binding each of the board's digits to exactly one of them
    forces exactly `len(values) - len(cells)` cells to their second slot —
    the S-cell count per house EMERGES, nothing here states it.
    """
    slots = flatten_slots(cells)
    for digit in engine.board.values:
        holds_digit = engine.reify_holds(slots, digit, label)
        engine.model.add(sum(holds_digit) == 1)


def emit_distinct_group(
    engine: Engine, cells: list[list[cp_model.IntVar]], *, label: str
) -> None:
    """Rule: every cell in `cells` holds a different digit. With no
    `schrodinger` layer in the stack, every cell's content stays width 1 and
    this is a plain `add_all_different`. With `schrodinger` present, `is_s`
    rides in through `engine.is_s()` (never a direct reference to that layer)
    and the is_S-gated counting rule `emit_house` builds fires instead, over
    content already widened to length 2 by the time this runs in phase 2.

    Called by `distinct.DistinctOverGroups` for each group of its partition —
    the one home every distinct rule (rows, cols, regions, the diagonals, and
    windoku's extra regions) closes a group of cells through.
    """
    if engine.is_s() is None:
        engine.model.add_all_different([sole(content) for content in cells])
    else:
        emit_house(engine, cells, label=label)


def abs_diff_var(
    engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar, *, suffix: str
) -> cp_model.IntVar:
    """Mint one fresh aux var `d == |a - b|`, self-named from the pair's own
    variable names plus `suffix` (e.g. `differs_by`'s `.diff`, whisper's
    `.gap`) since neither caller's `rel` carries a label of its own.

    `d`'s span must cover the widest possible `|a - b|`, read off each
    operand's own declared bounds rather than the board's raw digit range: a's
    or b's value_expr may be a doubler's `2*value` or an S-cell's `s_value`,
    both wider than a bare digit. `list(...)` first — the raw proto
    container's own negative indexing is unreliable.

    The one home for this mint: `pair_difference.differs_by` and
    `line._whisper` both need `d == |a - b|` as the first step of an
    otherwise-different pin (`d == k` / `d != k` vs. `d >= k`), so the span
    computation and `add_abs_equality` call live here once rather than
    forking with the pin.
    """
    a_domain, b_domain = list(a.proto.domain), list(b.proto.domain)
    span = max(a_domain[-1] - b_domain[0], b_domain[-1] - a_domain[0])
    d = engine.model.new_int_var(0, span, f"{a.name}-{b.name}.{suffix}")
    engine.model.add_abs_equality(d, a - b)
    return d


def emit_over_pairs(
    engine: Engine,
    pairs: list[tuple[cp_model.IntVar, cp_model.IntVar]],
    rel: Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None],
) -> None:
    """Rule: `rel(engine, a, b)` holds for every pair in `pairs` — the walk
    behind a many-cell path decomposed into consecutive pairs, `line.py`'s
    whisper relation's real user. A binary pair relation (`pair-difference`,
    `pair-ratio`, both via `PairRelation`) names exactly two cells and
    applies its `rel` to them directly, with no walk of its own.

    A callback rather than a relation-as-data table: the relation a thermo
    edge wants (a strict or non-strict inequality) is native CP-SAT —
    `model.add(a < b)` — so encoding it as an AllowedAssignments table would
    trade a direct primitive for indirection with nothing gained (ADR-0001
    keeps the engine seam raw OR-Tools). `rel` closes over whatever per-clue
    data it needs; this helper never learns clue or path structure, so a
    future path-shaped variant can decompose its own path into consecutive
    pairs before calling it.
    """
    for a, b in pairs:
        rel(engine, a, b)


def emit_indexed_position_match(
    engine: Engine,
    control: str,
    line: Sequence[str],
    match_terms: Callable[[str], list[cp_model.IntVar]],
) -> None:
    """Rule: for every position `p` on `line`, if `control` holds the digit
    `p` then `match_terms(line[p - 1])` holds — at least one of the bools that
    callback mints is true.

    The widening-aware shape of "a control cell's own digit names a position
    on a line, and that line's cell at the position must match something"
    (ADR-0019 decision 4): the control **indexes from every real digit it
    holds**, so a widened control holding `{a, b}` makes its demand at
    position `a` and at position `b` alike. Realized as one implication per
    position per control slot — `reify_holds` plus
    `add_bool_or(...).only_enforce_if(...)`, the house-rule idiom.

    The control's slots come through `engine.real_digit_values`, whose
    `real_digit_slots` base explains why a non-S-cell's sentinel second slot
    drops out of every term on its own, with no `is_s` gate here.

    What "match" means is the clue's, not this walk's, so it arrives as
    `match_terms` — `indexing` asks the line cell to hold the control's own
    coordinate, `numbered_rooms` asks it to share a digit with an outside
    cell. The two clues share the walk and nothing else; the callback is the
    seam between them, as `rel` is for `emit_over_pairs`.

    A control digit that names no position on `line` is the caller's to
    refuse: this walk fires no implication for it, so a clue that wants such
    a digit rejected states that bound itself.
    """
    control_slots = engine.real_digit_values(control)
    for position, address in enumerate(line, start=1):
        control_holds = engine.reify_holds(
            control_slots, position, f"{control}.holds{position}"
        )
        terms = match_terms(address)
        for indicator in control_holds:
            engine.model.add_bool_or(terms).only_enforce_if(indicator)
