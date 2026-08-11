"""The `cage` layer: no-repeats over a named cell set, no cover pressure.

A cage clue names a set of cells and forbids a repeat among them — unlike a
region (`rows-distinct`, `cols-distinct`, `regions-distinct`), a cage does not
have to cover the whole digit domain, so a 7-cell cage on a 9-digit board is
legal. One stateless `cage` instance pulls every such constraint via
`constraints_of` and emits one no-repeats rule per clue, structured like
`pair-sum` (a clue-looping layer), not like the partition-driven
`DistinctOverGroups` — no shared base with it.

A `distinct-over: "digit" | "value"` param picks what a repeat means, `"digit"`
the default:

- A **digits-distinct** cage forbids two cells holding the same *digit* — the
  classic killer rule, over the placed symbols. It reads every content slot
  raw (both of an S-cell's, `d1`'s sentinel keeping a non-S cell's second slot
  out of the way) into one `add_all_different`. With no `schrodinger` layer
  every cell is width 1, so this is the identical plain `add_all_different`
  `DistinctOverGroups` already emits.
- A **values-distinct** cage forbids two cells holding the same *value*. It
  reads each cell's value through `Engine.value_expr` (ADR-0009), blind to how
  that value was built: a plain cell's digit, a doubler's `modifier_value`, an
  S-cell's `s_value` — the value channel each producing layer reifies for
  itself. Same value always collides — a doubler worth 18 and an S-cell reading
  18 clash, since a value is just a number. The cage defines no value of its
  own; it only reads.

Neither mode adds cover pressure, so a cage never forces a cell to become an
S-cell.

An optional `name` param is accepted and reserved for future killer keying;
unread today.

A killer sum (S-aware and modifier-aware): an optional `value` param, when
present and `> 0`, additionally emits `sum(cells) == value`. Each cell
contributes, in order: its `modifier_value` (a discovered doubler's `2·d0`)
when the modifier layer reified one for that cell; else, once an S-cell pin
has widened it, both of its digits; else its one raw digit. The fold always
runs regardless of `distinct-over` (ADR-0008 decision 4, ADR-0009 decision
6) — the killer sum and the no-repeats mode answer to different rules.
`_cage_sum_term` reads `modifier_value` and `is_s`, the same
structure-registry facts the no-repeats half above tolerates the absence
of, so a cage with neither `doubler` nor `schrodinger` in the stack sums
each cell's sole content variable directly. Absent `value` or `value == 0`
(SudokuMaker's own no-sum cage) stays region-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, MalformedPuzzleError


def _cage_sum_term(
    engine: Engine,
    address: str,
    is_s: dict[str, cp_model.IntVar] | None,
    modifier_value: dict[str, cp_model.IntVar],
) -> cp_model.IntVar | cp_model.LinearExprT:
    """This cage cell's contribution to a killer sum: its `modifier_value`
    (a discovered doubler's `2·d0`) when the modifier layer reified one for
    this cell; else its one digit, or, once an S-cell pin has widened it,
    both — reified on `is_s` since which case applies is a solve-time fact,
    not something `emit` can branch on directly. A cell neither `doubler`
    nor `schrodinger` ever touched stays a plain content read."""
    if address in modifier_value:
        return modifier_value[address]
    contents = engine.contents(address)
    if len(contents) == 1:
        return contents[0]
    d0, d1 = contents
    # A width-2 cell only exists when schrodinger widened it, so is_s is present
    # here — width-1 cells (no schrodinger) never reach this line.
    s = cast("dict[str, cp_model.IntVar]", is_s)[address]
    board = engine.board
    term = engine.model.new_int_var(
        min(board.values), 2 * max(board.values), f"{address}.cage-sum-term"
    )
    engine.model.add(term == d0 + d1).only_enforce_if(s)
    engine.model.add(term == d0).only_enforce_if(s.negated())
    return term


@dataclass
class Cage:
    name: str = "cage"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        is_s = engine.is_s()
        modifier_value = cast(
            "dict[str, cp_model.IntVar]", engine.structures.get("modifier_value", {})
        )
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object), narrowed by cast.
            # `name`, if present, is reserved and unread.
            addresses = cast("list[str]", clue.params["cells"])
            distinct_over = cast("str", clue.params.get("distinct-over", "digit"))
            if distinct_over == "digit":
                slots = [
                    slot for address in addresses for slot in engine.contents(address)
                ]
                engine.model.add_all_different(slots)
            elif distinct_over == "value":
                keys = [engine.value_expr(address) for address in addresses]
                engine.model.add_all_different(keys)
            else:
                msg = (
                    "cage distinct-over must be 'digit' or 'value', got "
                    f"{distinct_over!r}"
                )
                raise MalformedPuzzleError(msg)
            value = clue.params.get("value")
            if value:
                total = cast("int", value)
                terms = [
                    _cage_sum_term(engine, address, is_s, modifier_value)
                    for address in addresses
                ]
                engine.model.add(sum(terms) == total)
