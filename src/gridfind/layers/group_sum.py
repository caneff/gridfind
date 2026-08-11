"""The `group-sum` layer: sum as an N-ary reduction, total only.

A group-sum clue names any number of cells (N >= 2) whose contents must add
to a target. One stateless `group-sum` instance pulls every such constraint
via `constraints_of` and emits one sum-rule per clue — structured like
`pair-sum` and the killer-sum half of `cage` (a clue-looping layer), not like
the partition-driven region layer.

Emits only the total: `sum(cells) == total`, never an `add_all_different`. A
bare group-sum therefore permits repeats among its cells — a non-house sum of
10 over two cells may be met as 5+5. Uniqueness, where a setter wants it, is
a separate capability composed alongside this one, not folded into it.

S-blind by decision, matching the cage's killer sum: reads the singular
`content()` seam and raises "not Schrödinger-ready yet" the moment a named
cell is a widened S-cell, rather than guessing which of its two digits
counts. `pair-sum` and `cage` are untouched by this layer — `group-sum` is
purely additive, registered beside them (their own fold-in is later work).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine


@dataclass
class GroupSum:
    name: str = "group-sum"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object), narrowed by cast.
            addresses = cast("list[str]", clue.params["cells"])
            total = cast("int", clue.params["sum"])
            engine.model.add(
                sum(engine.content(address) for address in addresses) == total
            )
