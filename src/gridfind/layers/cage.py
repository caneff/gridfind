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
  classic killer rule, over the placed symbols. It reads every cell's real
  digit slots through `Engine.real_digit_values` (both of an S-cell's; a non-S
  cell's `d1` sentinel is explained at its `real_digit_slots` base, not here)
  into one
  `add_all_different`. With no `schrodinger` layer every cell is width 1, so
  this is the identical plain `add_all_different` `DistinctOverGroups`
  already emits.
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

A killer cage's total is not this layer's concern: it is a `group-sum` over
the same cells, composed alongside a `cage` rather than bundled into one
(ADR-0009). This layer states no sum and reads no `value` param.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine, MalformedPuzzleError


@dataclass
class Cage:
    """A no-repeats-among-named-cells clue, over digits or over values per
    `distinct-over`; states no sum and no cover pressure of its own."""

    name: str = "cage"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # `name`, if present, is reserved and unread.
            addresses = engine.cell_addresses(clue)
            distinct_over = cast("str", clue.params.get("distinct-over", "digit"))
            if distinct_over == "digit":
                slots = [
                    var
                    for address in addresses
                    for var in engine.real_digit_values(address)
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
