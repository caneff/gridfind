"""The `group-sum` layer: sum as an N-ary reduction, total only.

A group-sum clue names any number of cells (N >= 2) whose contents must add
to a target. One stateless `group-sum` instance pulls every such constraint
via `constraints_of` and emits one sum-rule per clue — a clue-looping layer
structured like `cage`, not like the partition-driven region layer. The
`x`/`v` aliases resolve onto it too: an X clue is a group-sum of 10, a V
clue a group-sum of 5, each still passing its own two cells through
(expanded in `layers/__init__`).

Emits only the total: `sum(cells) == total`, never an `add_all_different`. A
bare group-sum therefore permits repeats among its cells — a non-house sum of
10 over two cells may be met as 5+5. Uniqueness, where a setter wants it, is
a separate capability composed alongside this one, not folded into it — a
killer cage is a `cage` (no-repeats) plus a `group-sum` (the total) over the
same cells, not one bundled layer (spec #240).

S-blind by decision: reads the singular `content()` seam and raises "not
Schrödinger-ready yet" the moment a named cell is a widened S-cell, rather
than guessing which of its two digits counts.

Arithmetic reads value, not digit: with a modifier layer (`doubler`) in the
stack, a named cell's `"modifier_value"` structure — the digit, or the
puzzle's declared fold when the solver discovers that cell as the modifier —
stands in for its raw digit. Absent that structure (no modifier layer), the
sum reads each cell's `content()` — the raw digit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine


@dataclass
class GroupSum:
    name: str = "group-sum"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        modifier_value = cast(
            "dict[str, cp_model.IntVar]", engine.structures.get("modifier_value", {})
        )
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object), narrowed by cast.
            addresses = cast("list[str]", clue.params["cells"])
            total = cast("int", clue.params["sum"])
            terms = [
                modifier_value.get(address, engine.content(address))
                for address in addresses
            ]
            engine.model.add(sum(terms) == total)
