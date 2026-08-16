"""The `pair-difference` relation: the second explicit-pair variant (decision 5), a
`PairRelation` relation-emitter.

A pair-difference clue names two cells whose values must differ, in
absolute value, by a target `k` — kropki-white / consecutive is the `k = 1`
case, though no setter-facing alias is added here. `differs_by` is the
relation-emitter `LAYER_REGISTRY["pair-difference"]` builds its `PairRelation`
with: given a clue's params, it reads the target `diff` and returns the
`rel` that pins one pair to it.

Deliberately narrow, mirroring `group-sum`'s two-cell case: the constraint
names both cells outright — a **pair**, not a **domino** — and the relation
never asks whether they are adjacent. Positive-only: only named
pairs are constrained. The relation is absolute, not directed — either cell
may hold the larger value — encoded with CP-SAT's native `add_abs_equality`
rather than a hand-built disjunction or a truth table, per the ISS-deviation
call in `docs/reference/iss-design-decisions.md` §1.5: CP-SAT propagates the
primitive itself, so there is nothing a table would buy.

Reads each cell's value through `PairRelation`'s `engine.value_expr` seam
(ADR-0009) — a plain digit, a doubler's `2·value`, or an S-cell's combined
`s_value` — never a raw content slot, so it carries no `s_blind` flag and
composes with a doubler or Schrödinger board.
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
        # The aux var's span must cover the widest possible |a - b|, read off
        # each operand's own declared bounds rather than the board's raw
        # digit range: a's or b's value_expr may be a doubler's 2·value or an
        # S-cell's s_value, both wider than a bare digit. `list(...)` first —
        # the raw proto container's own negative indexing is unreliable.
        a_domain, b_domain = list(a.proto.domain), list(b.proto.domain)
        span = max(a_domain[-1] - b_domain[0], b_domain[-1] - a_domain[0])
        d = engine.model.new_int_var(0, span, f"{a.name}-{b.name}.diff")
        engine.model.add_abs_equality(d, a - b)
        engine.model.add(d == target)

    return rel
