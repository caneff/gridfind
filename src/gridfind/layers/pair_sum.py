"""The `pair-sum` layer: the first real data-bearing variant (issue #66).

A pair-sum clue names two cells whose contents must add to a target. One
stateless `pair-sum` instance pulls every such constraint via `constraints_of`
and emits one sum-rule per clue, so a puzzle's many clues resolve to this
single layer (issue #65). The XV variant is spelled on top of it as an alias: an X clue
is a pair-sum of 10, a V clue a pair-sum of 5 (expanded in `layers/__init__`).

Deliberately narrow (issue #66): the constraint names both cells outright — a
**pair**, not a **domino**. The layer sums the named pair and never asks whether
its cells are adjacent (that geometry is #43). Positive-only: only named pairs
are constrained; the negative rule forbidding *unmarked* adjacent pairs from
summing to 5 or 10 needs board-wide adjacency and is out of scope. The rule is
emitted directly, like the prototype's cage sum; a shared pairwise-relation
helper (#42) waits for a second two-cell variant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine


@dataclass
class PairSum:
    name: str = "pair-sum"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — narrow to this clue's
            # shape: a pair of cell addresses and its target sum.
            addresses = cast("list[str]", clue.params["cells"])
            total = cast("int", clue.params["sum"])
            pair = [engine.cells[address].content[0] for address in addresses]
            engine.model.add(sum(pair) == total)
