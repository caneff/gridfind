"""The `cage` layer: no-repeats over a named cell set, no cover pressure.

A cage clue names a set of cells and forbids a repeat among them — unlike a
region (`rows-distinct`, `cols-distinct`, `regions-distinct`), a cage does not
have to cover the whole digit domain, so a 7-cell cage on a 9-digit board is
legal. One stateless `cage` instance pulls every such constraint via
`constraints_of` and emits one no-repeats rule per clue, structured like
`group-sum` (a clue-looping layer), not like the partition-driven
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

A killer sum through the same seam: an optional `value` param, when present
and `> 0`, additionally emits `sum(cells) == value`, each cell contributing
its `Engine.value_expr` — a doubler's `2·d0`, an S-cell's combined `s_value`,
else its plain digit. That is the one value the seam defines for every reader,
so the sum and the values-distinct half read a cell the same way and never a
second hand-rolled encoding (ADR-0009 decision 2). The sum runs regardless of
`distinct-over` (ADR-0008 decision 4, ADR-0009 decision 6) — sum and no-repeats
answer to different rules but share the one value. A doubled S-cell has no
defined value, so `value_expr` raises rather than sum it (ADR-0009 decision 5).
Absent `value` or `value == 0` (SudokuMaker's own no-sum cage) stays
region-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine, MalformedPuzzleError


@dataclass
class Cage:
    name: str = "cage"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
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
                terms = [engine.value_expr(address) for address in addresses]
                engine.model.add(sum(terms) == total)
