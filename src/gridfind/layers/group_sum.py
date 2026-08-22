"""The `group-sum` layer: sum as an N-ary reduction, total only.

A group-sum clue names any number of cells (N >= 2) whose contents must add
to a target. One stateless `group-sum` instance pulls every such constraint
via `constraints_of` and emits one sum-rule per clue — a clue-looping layer
structured like `cage`, not like the partition-driven region layer. The
`x`/`v` aliases resolve onto it too: an X clue is a group-sum of 10, a V
clue a group-sum of 5, each still passing its own two cells through
(expanded in `layers/__init__`).

Emits only the total: `sum(cells) == total`, or, when a clue's `negate` is
true, `sum(cells) != total` instead — never an `add_all_different`. A bare
group-sum therefore permits repeats among its cells — a non-house sum of 10
over two cells may be met as 5+5. Uniqueness, where a setter wants it, is
a separate capability composed alongside this one, not folded into it — a
killer cage is a `cage` (no-repeats) plus a `group-sum` (the total) over the
same cells, not one bundled layer (ADR-0009).

The negated mode is the XV negative rule's mechanism
(`sudokumaker.edge_clues`): the same emitter, applied over every unmarked
orthogonally-adjacent pair, once per value in the wire's `negative` list, so
positive and negative XV clues can never drift onto two different notions of
"sums to `s`".

Reads each cell's value through `Engine.value_expr` (ADR-0009), blind to how
that value was built: a plain cell's digit, a doubler's `modifier_value`, an
S-cell's combined `s_value` — the value channel each producing layer reifies
for itself. group-sum knows nothing of modifiers or Schrödinger cells; it sums
the one value the seam defines, so a killer cage's sum reads a cell exactly as
its values-distinct half does, never a second hand-rolled encoding. A doubled
S-cell is worth `2·s_value` through that same seam (ADR-0010), summed like any
other value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine


@dataclass
class GroupSum:
    """A clue that sums (or, when `negate` is set, forbids summing) its named
    cells' values to a target total; states no distinctness of its own."""

    name: str = "group-sum"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            addresses = engine.cell_addresses(clue)
            total = cast("int", clue.params["sum"])
            terms = [engine.value_expr(address) for address in addresses]
            if clue.params.get("negate", False):
                engine.model.add(sum(terms) != total)
            else:
                engine.model.add(sum(terms) == total)
