"""The `pair-difference` layer: the second explicit-pair variant (#42
decision 5), landing alongside the `emit_over_pairs` extraction (#128).

A pair-difference clue names two cells whose contents must differ, in
absolute value, by a target `k` — kropki-white / consecutive is the `k = 1`
case, though no setter-facing alias is added here. One stateless `pair-diff`
instance pulls every such constraint via `constraints_of` and emits one
difference-rule per clue, exactly like `pair-sum`.

Deliberately narrow, mirroring `pair-sum` (#66): the constraint names both
cells outright — a **pair**, not a **domino** — and the layer never asks
whether they are adjacent (that geometry is #43). Positive-only: only named
pairs are constrained. The relation is absolute, not directed — either cell
may hold the larger value — encoded with CP-SAT's native `add_abs_equality`
rather than a hand-built disjunction or a truth table, per the ISS-deviation
call in `docs/reference/iss-design-decisions.md` §1.5: CP-SAT propagates the
primitive itself, so there is nothing a table would buy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, sole
from gridfind.layers._base import emit_over_pairs


def _differs_by(
    target: int,
) -> Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None]:
    """A `rel` closing over one clue's target difference. Mints one fresh aux
    var `d` per pair, self-named from the pair's own variable names since
    `emit_over_pairs` carries no label: `d == |a - b|`, then pinned `d ==
    target`."""

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        span = max(engine.board.values) - min(engine.board.values)
        d = engine.model.new_int_var(0, span, f"{a.name}-{b.name}.diff")
        engine.model.add_abs_equality(d, a - b)
        engine.model.add(d == target)

    return rel


@dataclass
class PairDifference:
    name: str = "pair-difference"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — narrow to this
            # clue's shape: a pair of cell addresses and its target diff.
            addresses = cast("list[str]", clue.params["cells"])
            target = cast("int", clue.params["diff"])
            a, b = (sole(engine.contents(address)) for address in addresses)
            emit_over_pairs(engine, [(a, b)], _differs_by(target))
