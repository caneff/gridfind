"""The `pair-difference` relation: the second explicit-pair variant, a
`PairRelation` relation-emitter.

A pair-difference clue names two cells whose values must differ, in
absolute value, by a target `k` — kropki-white / consecutive is the `k = 1`
case, though no setter-facing alias is added here. `differs_by` is the
relation-emitter `LAYER_REGISTRY["pair-difference"]` builds its `PairRelation`
with: given a clue's params, it reads the target `diff` and returns the
`rel` that pins one pair to it — or, when `params["negate"]` is true, bars
the pair from it instead (`difference != k`). The negated mode is the
white-kropki negative rule's mechanism (`sudokumaker.edge_clues`): the same
emitter, applied over every unmarked orthogonally-adjacent pair, so positive
and negative clues can never drift onto two different notions of "differs by
k".

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
from gridfind.layers._base import abs_diff_var
from gridfind.puzzle import JsonValue


def differs_by(
    params: Mapping[str, JsonValue],
) -> Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None]:
    """The pair-difference relation-emitter: reads the clue's target `diff`
    and returns a `rel` closing over it. `rel` mints one fresh aux var `d ==
    |a - b|` per pair via `abs_diff_var` (the shared mint `line._whisper`
    also rides), then pins it to `d == target` — or, when `params["negate"]`
    is true, bars it from that value instead (`d != target`), absent/false
    otherwise."""
    target = cast("int", params["diff"])
    negate = bool(params.get("negate", False))

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        d = abs_diff_var(engine, a, b, suffix="diff")
        if negate:
            engine.model.add(d != target)
        else:
            engine.model.add(d == target)

    return rel
