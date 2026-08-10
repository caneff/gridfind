"""The `cage` layer: no-repeats over a named cell set, no cover pressure
(issue #157, spec #156 decision #150).

A cage clue names a set of cells and forbids a digit repeat among them —
unlike a region (`rows-distinct`, `cols-distinct`, `regions-distinct`), a
cage does not have to cover the whole digit domain, so a 7-cell cage on a
9-digit board is legal. One stateless `cage` instance pulls every such
constraint via `constraints_of` and emits one no-repeats rule per clue,
structured like `pair-sum` (a clue-looping layer), not like the
partition-driven `DistinctOverGroups` — no shared base with it.

The rule is a single `add_all_different` over the cage's is_S-gated slots,
read through the plural `contents()` seam (the same slot-gathering
`emit_house` uses for the cover rule): with no `schrodinger` layer, every
cell's content is width 1, so this is the identical plain `add_all_different`
`DistinctOverGroups` already emits with no `schrodinger` layer present. With
`schrodinger` present, the rule runs over both of a cage cell's slots — its
`d1` sentinel keeps a non-S cell's second slot out of the way, and an S-cell's
two real digits are both bound into the no-repeats set. Unlike `emit_house`,
this states no per-digit count, so it adds no cover pressure and never forces
a cell to become an S-cell.

An optional `name` param is accepted and reserved for future killer keying;
unread today.

A killer sum (issue #196): an optional `value` param, when present and `> 0`,
additionally emits `sum(cells) == value` read through the singular `content()`
seam — matching `pair-sum`'s precedent, this is S-blind by decision: a killer
sum over an S-cell raises `"not Schrödinger-ready yet"` rather than guessing
which of its two digits counts, while the no-repeats half above stays
Schrödinger-ready as-is. Future path (not built): an S-cell would eventually
contribute both its digits to the sum, its value settled by the Schrödinger
layer elsewhere — left for when a real link needs it. Absent `value` or
`value == 0` (SudokuMaker's own no-sum cage) stays region-only, exactly as
before.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine


@dataclass
class Cage:
    name: str = "cage"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — narrow to this
            # clue's shape: the cage's cells, and an optional killer sum.
            # `name`, if present, is reserved and unread.
            addresses = cast("list[str]", clue.params["cells"])
            slots = [slot for address in addresses for slot in engine.contents(address)]
            engine.model.add_all_different(slots)
            value = clue.params.get("value")
            if value:
                total = cast("int", value)
                engine.model.add(
                    sum(engine.content(address) for address in addresses) == total
                )
