"""The `pair-sum` layer: the first real data-bearing variant.

A pair-sum clue names two cells whose contents must add to a target. One
stateless `pair-sum` instance pulls every such constraint via `constraints_of`
and emits one sum-rule per clue, so a puzzle's many clues resolve to this
single layer. The XV variant is spelled on top of it as an alias: an X clue
is a pair-sum of 10, a V clue a pair-sum of 5 (expanded in `layers/__init__`).

Deliberately narrow: the constraint names both cells outright — a
**pair**, not a **domino**. The layer sums the named pair and never asks whether
its cells are adjacent. Positive-only: only named pairs
are constrained; the negative rule forbidding *unmarked* adjacent pairs from
summing to 5 or 10 needs board-wide adjacency and is out of scope. The rule
emits through the shared `emit_over_pairs` helper (decision 5), its target
sum riding in via the `rel` closure.

Arithmetic reads value, not digit: with a modifier
layer (`doubler`) in the stack, a named cell's `"modifier_value"`
structure — the digit, or the puzzle's declared fold when the solver discovers
that cell as the modifier — stands in for its raw digit. Absent that structure
(no modifier layer), the sum reads each cell's `content()` — the raw digit.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.layers._base import emit_over_pairs


def _sums_to(total: int) -> Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None]:
    """A `rel` closing over one clue's target sum."""

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        engine.model.add(a + b == total)

    return rel


@dataclass
class PairSum:
    name: str = "pair-sum"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        modifier_value = cast(
            "dict[str, cp_model.IntVar]", engine.structures.get("modifier_value", {})
        )
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — narrow to this clue's
            # shape: a pair of cell addresses and its target sum.
            addresses = cast("list[str]", clue.params["cells"])
            total = cast("int", clue.params["sum"])
            a, b = (
                modifier_value.get(address, engine.content(address))
                for address in addresses
            )
            emit_over_pairs(engine, [(a, b)], _sums_to(total))
