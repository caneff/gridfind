"""The `numbered-rooms` layer: SudokuMaker's Numbered Rooms escape-the-grid
clue.

An outside cell governs the inner cells of its own row or column, read
outward-to-inward from the clue: the near cell's placed digit `N` names a
1-based position on that line, and the outside cell must hold the digit the
line holds at that `N`th position — `outside == line[N - 1]`.

`clue.params["cells"]` is `[outside, *line]`: index 0 the outside cell
(`outside_cells.OutsideCells` is the sole creator of that address, seeded
into every stack), the rest the line's cells ordered from the clue inward —
`line[0]` is the near cell whose own digit names the position.

Reads the placed digit (`Engine.d0`/`Engine.real_digit_slots`), never
`value_expr` (ADR-0009's digit-read exception, mirroring `layers.indexing`) —
"digit `N` sits at the near cell" is a statement about the placed symbol, so
a doubler anywhere in the line is transparent to the rule.

With no widening layer in the stack (`engine.is_s()` is None) every cell is
one slot wide and a single `add_element` per clue realizes the rule directly,
native OR-Tools (ADR-0001) — the same element/involution primitive
`layers.indexing` uses for the 159 self-reference clue, reused rather than
reimplemented. Two things differ from `indexing`'s use of it: the index
selects into the clue's own ordered tail (never the control's own row or
column), and the target is the outside cell's placed digit (a variable)
rather than a fixed coordinate, which `add_element` already accepts.

With a widening layer in the stack, "the outside cell holds the digit at
position `N`" widens to **membership** over each cell's real digit slots
(ADR-0019 decision 4), and the near cell **indexes from every digit it
holds**. Both layers share that walk — `_base.emit_indexed_position_match`,
which owns the per-position implication and the sentinel reasoning behind
it; this layer supplies only the match, "the line cell at the position and
the outside cell share a real digit".

The outside cell is read as a digit set like any other cell: `outside-cells`
registers before `schrodinger`, which widens every cell already registered,
so a border-ring cell carries a second slot too and its match may come from
either one.

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

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.layers._base import emit_indexed_position_match


def _emit_width1_numbered_rooms_group(
    engine: Engine, outside: str, line: list[str]
) -> None:
    variables = [engine.d0(address) for address in line]
    index = engine.d0(line[0]) - 1
    target = engine.d0(outside)
    engine.model.add_element(index, variables, target)


def _require_a_named_position(engine: Engine, near: str, length: int) -> None:
    """Bound every real digit the near cell holds to `1..length`, a position
    on its own line. A gated slot (a widened cell's `d1`) carries the bound
    only while it holds a real digit."""
    for slot, guard in engine.real_digit_slots(near):
        bound = engine.model.add_linear_constraint(slot, 1, length)
        if guard is not None:
            bound.only_enforce_if(guard)


def _slot_match_terms(
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
    terms = []
    for (i, a), (j, b) in itertools.product(enumerate(left), enumerate(right)):
        same = engine.model.new_bool_var(f"{label}.{i}{j}")
        engine.model.add(a == b).only_enforce_if(same)
        engine.model.add(a != b).only_enforce_if(same.negated())
        terms.append(same)
    return terms


def _emit_s_aware_numbered_rooms_group(
    engine: Engine, outside: str, line: list[str]
) -> None:
    near = line[0]
    _require_a_named_position(engine, near, len(line))
    outside_digits = engine.real_digit_values(outside)

    def shares_a_digit_with_the_outside_cell(target: str) -> list[cp_model.IntVar]:
        return _slot_match_terms(
            engine,
            engine.real_digit_values(target),
            outside_digits,
            f"{target}.shares.{outside}",
        )

    emit_indexed_position_match(
        engine, near, line, shares_a_digit_with_the_outside_cell
    )


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
