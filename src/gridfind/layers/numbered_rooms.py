"""The `numbered-rooms` layer: SudokuMaker's Numbered Rooms escape-the-grid
clue.

An outside cell governs the inner cells of its own row or column, read
outward-to-inward from the clue: the near cell's placed digit `N` names a
1-based position on that line, and the outside cell must hold the digit the
line holds at that `N`th position — `outside == line[N - 1]`, the same
element/involution primitive `layers.indexing` already realizes for the 159
self-reference clue (ADR-0019, the shared `add_element` seam), reused here
rather than reimplemented. Two things differ from `indexing`'s use of the
seam: the index selects into the clue's own ordered tail (never the
control's own row/column), and the target is the outside cell's placed digit
(a variable) rather than a fixed row/column number — `add_element` already
accepts a variable target, so no second primitive is needed.

Reads the placed digit (`Engine.d0`/`Engine.real_digit_slots`), never
`value_expr` (ADR-0009's digit-read exception, mirroring `layers.indexing`) —
"digit `N` sits at the near cell" is a statement about the placed symbol, so
a doubler anywhere in the line is transparent to the rule.

`clue.params["cells"]` is `[outside, *line]`: index 0 the outside cell
(`outside_cells.OutsideCells` is the sole creator of that address, seeded
into every stack), the rest the line's cells ordered from the clue inward —
`line[0]` is the near cell whose own digit names the position.

With no widening layer in the stack (`engine.is_s()` is None) every cell is
one slot wide and a single `add_element` per clue realizes the rule
directly, native OR-Tools (ADR-0001). `add_element` also bounds its own
index into `0..len(line) - 1`, so a near cell may not hold a digit that
names no position on the line.

With a widening layer in the stack, "the outside cell holds the digit at
position `N`" widens to **membership** over each cell's real digit slots
(ADR-0019 decision 4), and the near cell **indexes from every digit it
holds** — a near cell holding `{a, b}` demands a match at position `a` and
at position `b`. Realized per line position `p`: "the near cell holds `p`"
⟹ "the line cell at `p` and the outside cell share a real digit"
(`engine.reify_holds` + `add_bool_or(...).only_enforce_if(...)`, the
house-rule idiom `indexing` uses for the same shape). The outside cell is
read through `real_digit_slots` like any other: `outside-cells` registers
before `schrodinger`, which widens every cell already registered, so a
border-ring cell carries a second slot too and its match may come from
either one.

Both sides read their slots through `engine.real_digit_values`, whose
`real_digit_slots` base explains a non-S-cell's second slot as a per-cell
sentinel above every real digit: it matches no position, and no other cell's
slot, so it drops out of every term on its own with no explicit `is_s` gate.

Every real digit the near cell holds must name a position — `1` through the
line's length — enforced directly on its slots, the widening-aware statement
of the bound `add_element` imposes on the single-slot path. It refuses both
ends: `0`, which names no position on any line, and a digit past the line's
last cell, which a domain wider than the board (exactly what a widening
layer needs) can otherwise offer. A near cell forced to such a digit reads
broke rather than falling silently satisfied for want of a position to fire
on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine


def _emit_width1_numbered_rooms_group(
    engine: Engine, outside: str, line: list[str]
) -> None:
    variables = [engine.d0(address) for address in line]
    index = engine.d0(line[0]) - 1
    target = engine.d0(outside)
    engine.model.add_element(index, variables, target)


def _require_a_named_position(
    engine: Engine,
    slots: Sequence[tuple[cp_model.IntVar, cp_model.IntVar | None]],
    length: int,
) -> None:
    """Bound every real digit the near cell holds to `1..length`, a position
    on its own line. A gated slot (a widened cell's `d1`) carries the bound
    only while it holds a real digit."""
    for slot, guard in slots:
        bound = engine.model.add_linear_constraint(slot, 1, length)
        if guard is not None:
            bound.only_enforce_if(guard)


def _reify_shares_a_digit(
    engine: Engine,
    left: Sequence[cp_model.IntVar],
    right: Sequence[cp_model.IntVar],
    label: str,
) -> list[cp_model.IntVar]:
    """One reified bool per `(left slot, right slot)` pair, true only when the
    two slots hold the same digit — the terms an `add_bool_or` reads as "these
    two cells share a real digit". A sentinel slot never matches: it sits
    above every real digit and no two cells share one, so a pair naming one
    can never be the term that satisfies the or."""
    shared = []
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            same = engine.model.new_bool_var(f"{label}.{i}{j}")
            engine.model.add(a == b).only_enforce_if(same)
            engine.model.add(a != b).only_enforce_if(same.negated())
            shared.append(same)
    return shared


def _emit_s_aware_numbered_rooms_group(
    engine: Engine, outside: str, line: list[str]
) -> None:
    near = line[0]
    near_slots = engine.real_digit_slots(near)
    _require_a_named_position(engine, near_slots, len(line))
    near_digits = [slot for slot, _guard in near_slots]
    outside_digits = engine.real_digit_values(outside)
    for position, address in enumerate(line, start=1):
        near_holds = engine.reify_holds(
            near_digits, position, f"{near}.holds{position}"
        )
        shared = _reify_shares_a_digit(
            engine,
            engine.real_digit_values(address),
            outside_digits,
            f"{address}.shares.{outside}.at{position}",
        )
        for indicator in near_holds:
            engine.model.add_bool_or(shared).only_enforce_if(indicator)


def _emit_numbered_rooms_group(engine: Engine, outside: str, line: list[str]) -> None:
    if engine.is_s() is None:
        _emit_width1_numbered_rooms_group(engine, outside, line)
        return
    _emit_s_aware_numbered_rooms_group(engine, outside, line)


@dataclass
class NumberedRooms:
    """SudokuMaker's Numbered Rooms clue: an outside cell holds the digit its
    row/column's near-to-far line holds at the position the near cell's own
    digit names."""

    name: str = "numbered-rooms"
    depends_on: tuple[str, ...] = ("board", "outside-cells")

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            cells = cast("list[str]", clue.params["cells"])
            outside, line = cells[0], cells[1:]
            _emit_numbered_rooms_group(engine, outside, line)
