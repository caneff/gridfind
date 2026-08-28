"""The `line` layer: the shared spine every SudokuMaker line relation
(renban, whisper, palindrome, between, region-sum, sequence, grouped-line,
lockout, double-arrow) rides — one layer kind, shaped like `Thermo`, plus a
per-alias relation table.

`LINE_RELATIONS` is the one growth point: each row is `(reading_mode,
predicate)`, keyed by the clue's own `params["relation"]` alias. `emit` owns
the three family-wide decisions once — the path read, the reading-mode seam
selection, and the Schrödinger digit-mode rule — so a new relation costs one
table row and one predicate, never a new layer or decode path. A
`"value"`-mode relation reads each path cell through `engine.value_expr`
(ADR-0009, precedence `modifier_value -> s_value -> digit`), so a doubler or
a Schrödinger cell on the line counts as its folded value, the same seam
`thermo` and the pair-relation family already read. A `"digit"`-mode relation
reads each path cell through `engine.real_digit_slots` (ADR-0019 dec 6)
instead — a list of `(digit, guard)` pairs per cell, `d0`'s guard always
`None`, `d1`'s the cell's `is_s` — the same gated seam `clone` reads a
digit-set clue through, so a Schrödinger cell on a set-structured digit
relation (renban) contributes both its digits, never folded to one `s_value`.

Whisper is the value-mode row: for each adjacent path pair, `|value_expr(i) -
value_expr(i+1)| >= params["minDifference"]` — German (5) and Dutch (4) are
this same relation at a different threshold. `minDifference` is read with a
bare subscript, so a clue missing it raises `KeyError` rather than falling
back to an invented default.

Renban is the first digit-mode row, and states nothing beyond the path: every
real digit slot distinct, and the run's spread (`max - min`) one less than
however many real slots the path actually carries — a Schrödinger cell's
extra, gated slot included, so a 2-cell path holding an S-cell can seat a
3-digit run.

Palindrome is the second digit-mode row, and the first **position-structured**
one: every mirror pair `(i, n-1-i)` of the path holds the same real digit, its
odd-length middle cell (read by no pair) left free. Position structure means
each cell must fold to one real digit before the mirror pairing runs, so
unlike renban's set-structured pooling a Schrödinger-widened cell has no
defined fold — `single_real_digits` raises through `sole` (`engine.py`)
rather than guess one. This is the shared position-structured Schrödinger
raise grouped-line reuses.

Grouped-line is the third digit-mode row, and the second position/window-
structured one (reusing `single_real_digits`, hence palindrome's same raise
on a Schrödinger-widened path cell): `params["groups"]` names digit-bitmask
groups partitioning the board, and every window of `len(groups)` consecutive
path cells holds one digit from each group — the one rule entropic, modular,
and parity all ride, keyed only by which groups they name. A partition with a
gap or overlap raises `MalformedPuzzleError` at emit, where the board's own
digit domain is in scope. The partition check and the digit-to-group-index
table live in `layers/bitmask_group.py` — the shared home window-groups also
imports from, for its own laxer, gap/overlap-tolerant validation and table
shape (`layers/window_groups.py`).

Between is the second value-mode row: the two path ends are the bulbs, every
interior cell strictly between them (`min(a, b) < value_expr(c) <
max(a, b)`). The ends only bound each other — no rule pins them together
beyond forming the interval — so a 2-cell path (no interior cell) asserts
nothing.

Sequence is a value-mode row: an arithmetic progression, every
successive `value_expr` difference equal (`value(c[i+1]) - value(c[i])`
constant across the path, any integer including 0 — a flat line is valid, no
distinctness). Chained directly off consecutive triples rather than through
one aux var per pair (`whisper`'s `abs_diff_var` mint): equal consecutive
differences is already a linear relation CP-SAT takes natively, so pinning
each triple's outer difference equal to its neighbour's needs no minted var.
Reversal-invariant — negating every difference leaves them equal to each
other — and a 1- or 2-cell path (fewer than two differences to compare)
asserts nothing.
Lockout is a value-mode row, and between's inverse: the two path
ends are the bulbs, which must differ by at least `size // 2` (`size` from
`engine.board.size`, never the wire), and every interior cell strictly
*outside* the closed bulb interval (`value_expr(c) < min(a, b)` or `>
max(a, b)`). `_bulb_bounds` mints the shared `min`/`max` aux-var pair both
between and lockout bound their interior cells against.

Double-arrow is the fourth value-mode row: the two path ends are the bulbs,
and the interior cells' values must sum to the two bulbs' own sum —
`sum(value_expr(interior)) == a + b` (ADR-0022, ratifying #670's research).
Reversal-invariant, since swapping the ends leaves both sides of the equation
unchanged. Unlike between and lockout, a 2-cell path (no interior) is not a
vacuous no-op: an empty interior sums to 0, which can never equal two
positive bulb values, so it reads broke as a plain consequence of the same
equality, needing no special case.

Region-sum is the fifth value-mode row, and the family's one **cross-relation**
seam: every other relation is closed over its own path, its knobs, and the
value/digit seam, but region-sum reaches past that to cross the existing
`region_map_for_constraints` door (`layers/regions.py`) and resolve the
board's own partition — a setter's jigsaw map, the classic box tiling, or
(with no `regions-distinct` constraint at all) one region covering the whole
board. It segments the ordered path against that partition **per visit**: a
fresh segment opens each time the path's region changes, so a line that
re-enters a region already visited is cut again rather than pooled into that
region's earlier segment, and every segment's `value_expr` sum must be equal.
Keyed by `singleRegionTotals` (ADR-0023): `False`, the default, is this
per-visit rule; `True` names per-region pooling, which is unmodeled, so it
raises rather than guess a rule the spec named out of scope. A one-region
board collapses the path to one segment regardless of its cells — vacuously
nothing to compare — so that case warns to stderr and asserts nothing rather
than silently pass every such puzzle.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import cast

from ortools.sat.python import cp_model

from gridfind.cell_geometry import format_address
from gridfind.engine import (
    Engine,
    GridfindError,
    sole,
    warn_dropped,
)
from gridfind.layers._base import abs_diff_var, emit_over_pairs
from gridfind.layers.bitmask_group import group_index_table, validate_partition
from gridfind.layers.regions import RegionMap, region_map_for_constraints
from gridfind.puzzle import Constraint as PuzzleConstraint
from gridfind.puzzle import JsonValue

ReadingMode = str  # "value" or "digit"
ValueSequence = list[cp_model.IntVar]
DigitSlot = tuple[cp_model.IntVar, cp_model.IntVar | None]
DigitSequence = list[list[DigitSlot]]
ValuePredicate = Callable[[Engine, ValueSequence, Mapping[str, JsonValue]], None]
DigitPredicate = Callable[[Engine, DigitSequence, Mapping[str, JsonValue]], None]
LinePredicate = ValuePredicate | DigitPredicate


def _whisper(
    engine: Engine,
    sequence: ValueSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Every adjacent path pair's values differ by at least `minDifference`.
    Mints one fresh aux var `d == |a - b|` per pair via `abs_diff_var`
    (`differs_by`'s shared mint), then pins it to `d >= minimum`."""
    minimum = cast("int", params["minDifference"])

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        d = abs_diff_var(engine, a, b, suffix="gap")
        engine.model.add(d >= minimum)

    emit_over_pairs(engine, list(pairwise(sequence)), rel)


def _bulb_bounds(
    engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar, *, suffix: str
) -> tuple[cp_model.IntVar, cp_model.IntVar]:
    """Mint fresh `low_var == min(a, b)`, `high_var == max(a, b)` aux vars,
    spanned off each bulb's own declared domain (`abs_diff_var`'s same
    reasoning, `_base.py`) rather than the board's raw digit range: a
    bulb's `value_expr` may be a doubler's `2*value` or an S-cell's
    `s_value`, both wider than a bare digit. Between and lockout both bound
    their interior cells against the same pair of bulbs this way — the one
    home for the mint, `suffix` keeping each relation's aux vars apart."""
    a_domain, b_domain = list(a.proto.domain), list(b.proto.domain)
    low = min(a_domain[0], b_domain[0])
    high = max(a_domain[-1], b_domain[-1])
    low_var = engine.model.new_int_var(low, high, f"{a.name}-{b.name}.{suffix}_low")
    high_var = engine.model.new_int_var(low, high, f"{a.name}-{b.name}.{suffix}_high")
    engine.model.add_min_equality(low_var, [a, b])
    engine.model.add_max_equality(high_var, [a, b])
    return low_var, high_var


def _between(
    engine: Engine,
    sequence: ValueSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """The two path ends are the bulbs `a, b`; every interior cell sits
    strictly between them: `min(a, b) < value_expr(c) < max(a, b)`. The
    bulbs only bound — no rule relates them to each other — so a 2-cell path
    (no interior) asserts nothing."""
    a, b = sequence[0], sequence[-1]
    interior = sequence[1:-1]
    if not interior:
        return
    low_var, high_var = _bulb_bounds(engine, a, b, suffix="between")
    for cell in interior:
        engine.model.add(cell > low_var)
        engine.model.add(cell < high_var)


def _sequence(
    engine: Engine,
    sequence: ValueSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Every successive `value_expr` difference along the path is equal — an
    arithmetic progression, common difference any integer including 0 (a
    flat line is valid, no distinctness). Pinned directly over each
    consecutive triple, `c - b == b - a`: with fewer than three cells there
    is no triple to pin, so a 1- or 2-cell path asserts nothing, and chaining
    every triple's equality transitively forces one constant difference
    across the whole path without minting an aux var per pair."""
    for a, b, c in zip(sequence, sequence[1:], sequence[2:], strict=False):
        engine.model.add(c - b == b - a)


def _lockout(
    engine: Engine,
    sequence: ValueSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Between's inverse: the two path ends are the bulbs `a, b`, which must
    differ by at least `size // 2` — `size` read from `engine.board.size`,
    never the wire (9x9 = 4, 6x6 = 3, 4x4 = 2; threshold ratified from spec
    and amended from a real 4x4 SudokuMaker link, ADR-0021).
    Every interior cell's value must sit strictly *outside* the closed
    bulb interval: `value_expr(c) < min(a, b)` or `> max(a, b)`, never
    equal to either end. Both halves read `min(a, b)`/`max(a, b)` of the
    pair rather than "first end, then second", so redrawing the line the
    other way gives the same verdict.

    The threshold reuses `abs_diff_var` (whisper's own mint); the interval
    reuses `_bulb_bounds` (between's own mint). "Outside the closed
    interval" is an either-or a bare conjunction can't express, so each
    interior cell reifies `below`/`above` booleans against the shared
    `low_var`/`high_var` and OR's them — the house
    `only_enforce_if`-pair-plus-`add_bool_or` idiom (`equality_cage.py`).
    A 2-cell path (no interior) only checks the threshold, same as
    between's bulbs-only-bound posture."""
    a, b = sequence[0], sequence[-1]
    interior = sequence[1:-1]
    threshold = engine.board.size // 2
    gap = abs_diff_var(engine, a, b, suffix="lockout_gap")
    engine.model.add(gap >= threshold)
    if not interior:
        return
    low_var, high_var = _bulb_bounds(engine, a, b, suffix="lockout")
    for cell in interior:
        below = engine.model.new_bool_var(f"{cell.name}.lockout_below")
        engine.model.add(cell < low_var).only_enforce_if(below)
        engine.model.add(cell >= low_var).only_enforce_if(below.negated())
        above = engine.model.new_bool_var(f"{cell.name}.lockout_above")
        engine.model.add(cell > high_var).only_enforce_if(above)
        engine.model.add(cell <= high_var).only_enforce_if(above.negated())
        engine.model.add_bool_or([below, above])


def _double_arrow(
    engine: Engine,
    sequence: ValueSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """The two path ends are the bulbs `a, b`; the interior cells' values must
    sum to the bulbs' own sum: `sum(value_expr(interior)) == a + b`
    (ADR-0022). Reversal-invariant — swapping the ends leaves both sides of
    the equation unchanged. A 2-cell path (no interior) sums its empty
    interior to 0, which can never equal two positive bulb values, so it
    reads broke without a separate check for the no-interior case."""
    a, b = sequence[0], sequence[-1]
    interior = sequence[1:-1]
    engine.model.add(sum(interior) == a + b)


def _region_index_by_address(region_map: RegionMap) -> dict[str, int]:
    """Every cell address the region map covers, mapped to its own region's
    index — the lookup `_region_sum` segments the ordered path against,
    built fresh off whatever partition `region_map_for_constraints` resolved
    (a setter's jigsaw map, the classic box tiling, or the one-whole-board
    fallback)."""
    return {
        format_address(row, col): index
        for index, region in enumerate(region_map)
        for row, col in region
    }


def _region_sum(
    engine: Engine,
    sequence: ValueSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Segment the ordered path at region boundaries, per visit — a fresh
    segment opens each time the path's `RegionMap` region changes, so a
    region already visited earlier in the path is cut again on re-entry,
    never pooled into its first segment — then assert every segment's
    `value_expr` sum equal (ADR-0023). `singleRegionTotals = True` names
    per-region pooling, unmodeled, so it raises rather than guess a rule the
    spec named out of scope. A one-whole-board region (no `regions-distinct`
    constraint on the puzzle at all) collapses the path to a single segment
    regardless of its cells — vacuously nothing to compare — so that case
    warns to stderr and asserts nothing instead of silently passing every
    such puzzle."""
    if cast("bool", params.get("singleRegionTotals", False)):
        msg = (
            "region-sum line with singleRegionTotals=true (per-region "
            "pooling) is not modeled"
        )
        raise GridfindError(msg)

    region_map = region_map_for_constraints(
        cast("Iterable[PuzzleConstraint]", engine.constraints), engine.board.size
    )
    if len(region_map) == 1:
        warn_dropped("region-sum line on a board with no region partition")
        return

    region_of = _region_index_by_address(region_map)
    path = cast("list[str]", params["path"])
    segments: list[list[cp_model.IntVar]] = []
    previous_region: int | None = None
    for address, value in zip(path, sequence, strict=True):
        region = region_of[address]
        if region != previous_region:
            segments.append([])
            previous_region = region
        segments[-1].append(value)

    if len(segments) < 2:
        return

    totals = [sum(segment) for segment in segments]
    for total in totals[1:]:
        engine.model.add(total == totals[0])


def _renban(
    engine: Engine,
    sequence: DigitSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Every real digit slot on the path distinct, and `max - min` one less
    than the count of real slots — a run of that many consecutive,
    non-repeating digits, owning its own distinctness (no cage/region
    needed).

    Distinctness rides the same sentinel trick `cage`'s `distinct-over:
    "digit"` mode uses (`layers/cage.py`): a non-S-cell's second slot sits on
    its own per-cell sentinel, always above every real digit, so a plain
    `add_all_different` over every raw slot — gated or not — already forbids
    a real repeat, no `only_enforce_if` needed. `min` needs no gating either,
    for the same reason: a sentinel can never be the smallest value present.

    `max` cannot take the same shortcut: a sentinel left in would inflate it.
    Each gated slot instead contributes a fresh var pinned to its own digit
    under its guard, the board's own floor otherwise — a value no real digit
    on the path can fall beneath, so it never wins a max it does not belong
    in. `slot_count` — one per path cell, plus one more per realized
    Schrödinger cell — is the same guard sum, read as a plain linear
    expression rather than reified.
    """
    board = engine.board
    low, high = board.values[0], board.values[-1]
    slots = [slot for cell in sequence for slot in cell]
    digits = [digit for digit, _ in slots]
    engine.model.add_all_different(digits)

    max_terms: list[cp_model.IntVar] = []
    for digit, guard in slots:
        if guard is None:
            max_terms.append(digit)
            continue
        term = engine.model.new_int_var(low, high, f"{digit.name}.renban_span")
        engine.model.add(term == digit).only_enforce_if(guard)
        engine.model.add(term == low).only_enforce_if(guard.negated())
        max_terms.append(term)

    slot_count = len(sequence) + sum(guard for _, guard in slots if guard is not None)
    minimum = engine.model.new_int_var(low, high, f"{digits[0].name}.renban_min")
    maximum = engine.model.new_int_var(low, high, f"{digits[0].name}.renban_max")
    engine.model.add_min_equality(minimum, digits)
    engine.model.add_max_equality(maximum, max_terms)
    engine.model.add(maximum - minimum == slot_count - 1)


def single_real_digits(sequence: DigitSequence) -> list[cp_model.IntVar]:
    """The position-structured Schrödinger raise: fold each path cell's real
    digit slots to its one real digit via `sole` (`engine.py`) before a
    position- or window-structured relation pairs or windows them. Renban's
    set-structured pooling quantifies over every real slot instead and never
    calls this. A cell Schrödinger-widened to two real slots has no defined
    fold — which slot the relation's rule would mean is not stated anywhere
    — so `sole` raises `GridfindError` loud rather than guess one. Palindrome
    is the first caller; grouped-line reuses this same fold, and
    `layers/window_groups.py`'s per-grid-cell fold is the third, public so
    that module can import it rather than hand-roll a second copy."""
    return [sole(cell)[0] for cell in sequence]


def _palindrome(
    engine: Engine,
    sequence: DigitSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Every mirror pair `(i, n-1-i)` holds the same real digit; an
    odd-length path's middle cell is read by neither pair and so stays free."""
    digits = single_real_digits(sequence)
    for i in range(len(digits) // 2):
        engine.model.add(digits[i] == digits[-1 - i])


def _grouped(
    engine: Engine,
    sequence: DigitSequence,
    params: Mapping[str, JsonValue],
) -> None:
    """Entropic / modular / parity, one rule: `params["groups"]` names `G`
    digit-bitmask groups partitioning the board (`validate_partition`), and
    every window of `G` consecutive path cells holds one digit from each
    group — the line cycles the partition.

    Window-structured like palindrome's mirror pairing, so it shares
    palindrome's Schrödinger raise: each path cell folds to its one real
    digit via `single_real_digits` before windowing, refusing loud on a
    multi-slot cell rather than guess which slot the window would mean.

    Each digit is mapped to its group index through a table constraint
    (`group_index_table`), then each window's `G` group-index vars are
    pinned all-different — with exactly `G` slots over a `0..G-1` domain,
    all-different already forces a bijection, i.e. every group hit exactly
    once, with no separate "exactly one" bookkeeping needed.
    """
    groups = cast("list[int]", params["groups"])
    validate_partition(groups, engine.board.values)

    digits = single_real_digits(sequence)
    group_count = len(groups)
    table = group_index_table(groups, engine.board.values)
    group_of = [
        engine.model.new_int_var(0, group_count - 1, f"{digit.name}.group")
        for digit in digits
    ]
    for digit, group in zip(digits, group_of, strict=True):
        engine.model.add_allowed_assignments([digit, group], table)
    for start in range(len(digits) - group_count + 1):
        engine.model.add_all_different(group_of[start : start + group_count])


LINE_RELATIONS: dict[str, tuple[ReadingMode, LinePredicate]] = {
    "whisper": ("value", _whisper),
    "renban": ("digit", _renban),
    "palindrome": ("digit", _palindrome),
    "grouped": ("digit", _grouped),
    "between": ("value", _between),
    "sequence": ("value", _sequence),
    "lockout": ("value", _lockout),
    "double-arrow": ("value", _double_arrow),
    "region-sum": ("value", _region_sum),
}


@dataclass
class Line:
    """One line kind for every relation `LINE_RELATIONS` names, dispatched by
    each clue's own `params["relation"]` — an unrecognized alias raises
    `KeyError` (`build_stack` accepts any `line` constraint; the relation
    table is where an unmodeled alias fails loud)."""

    name: str = "line"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            relation = cast("str", clue.params["relation"])
            reading_mode, predicate = LINE_RELATIONS[relation]
            path = cast("list[str]", clue.params["path"])
            if reading_mode == "value":
                value_sequence = [engine.value_expr(address) for address in path]
                cast("ValuePredicate", predicate)(engine, value_sequence, clue.params)
            elif reading_mode == "digit":
                digit_sequence = [engine.real_digit_slots(address) for address in path]
                cast("DigitPredicate", predicate)(engine, digit_sequence, clue.params)
            else:
                msg = (
                    f"{relation!r} line relation reads {reading_mode!r} mode, "
                    "not yet built"
                )
                raise NotImplementedError(msg)
