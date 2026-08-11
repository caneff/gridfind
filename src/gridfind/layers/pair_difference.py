"""The `pair-difference` relation: the second explicit-pair variant (#42
decision 5), now expressed as one `PairRelation` (issue #225) relation-emitter
rather than its own layer class.

A pair-difference clue names two cells whose contents must differ, in
absolute value, by a target `k` — kropki-white / consecutive is the `k = 1`
case, though no setter-facing alias is added here. `differs_by` is the
relation-emitter `LAYER_REGISTRY["pair-difference"]` builds its `PairRelation`
with: given a clue's params, it reads the target `diff` and returns the
`rel` that pins one pair to it.

Deliberately narrow, mirroring `pair-sum` (#66): the constraint names both
cells outright — a **pair**, not a **domino** — and the relation never asks
whether they are adjacent (that geometry is #43). Positive-only: only named
pairs are constrained. The relation is absolute, not directed — either cell
may hold the larger value — encoded with CP-SAT's native `add_abs_equality`
rather than a hand-built disjunction or a truth table, per the ISS-deviation
call in `docs/reference/iss-design-decisions.md` §1.5: CP-SAT propagates the
primitive itself, so there is nothing a table would buy.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.puzzle import JsonValue


def differs_by(
    params: Mapping[str, JsonValue],
) -> Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None]:
    """The pair-difference relation-emitter: reads the clue's target `diff`
    and returns a `rel` closing over it. `rel` mints one fresh aux var `d`
    per pair, self-named from the pair's own variable names since
    `emit_over_pairs` carries no label: `d == |a - b|`, then pinned `d ==
    target`."""
    target = cast("int", params["diff"])

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        span = max(engine.board.values) - min(engine.board.values)
        d = engine.model.new_int_var(0, span, f"{a.name}-{b.name}.diff")
        engine.model.add_abs_equality(d, a - b)
        engine.model.add(d == target)

    return rel
