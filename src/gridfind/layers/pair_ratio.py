"""The `pair-ratio` relation: black kropki, the
third explicit-pair variant expressed as a `PairRelation`
relation-emitter.

A pair-ratio clue names two cells whose values stand in a fixed integer
ratio `k`, undirected — either cell may hold the larger value. `ratio_of` is
the relation-emitter `LAYER_REGISTRY["pair-ratio"]` builds its `PairRelation`
with: given a clue's params, it reads the target `k` and returns the `rel`
that pins one pair to it — or, when `params["negate"]` is true, bars the
pair from it instead (neither `a == k*b` nor `b == k*a`). The negated mode
is the black-kropki negative rule's mechanism (`sudokumaker.edge_clues`):
the same emitter, applied over every unmarked orthogonally-adjacent pair, so
positive and negative clues can never drift onto two different notions of
"in ratio k".

`k` is a constant, so both `a == k*b` and `b == k*a` are linear — no
`add_multiplication_equality` needed. The undirected either-or is one
reified bool, mirroring the `schrodinger` layer's precedent
(`only_enforce_if(s)` / `only_enforce_if(s.negated())`) rather than a
hand-built disjunction or a truth table.

Deliberately narrow, mirroring `pair-difference`: a **pair**, not a
**domino** — the relation never asks whether the cells are adjacent — and positive-only,
carrying no implied distinctness (that
is `cage`'s job). A `k == 1` clue forces `a == b`, which resolves `broke`
under distinctness as a natural consequence of the rest of the stack, not a
case special-cased here.

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


def ratio_of(
    params: Mapping[str, JsonValue],
) -> Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None]:
    """The pair-ratio relation-emitter: reads the clue's target `k` and
    returns a `rel` closing over it. `rel` mints one fresh reified bool `s`
    per pair, self-named from the pair's own variable names since `rel`
    carries no label of its own, and pins `a == k*b` under `s`,
    `b == k*a` under its negation — undirected, either cell may hold the
    larger value. When `params["negate"]` is true, `rel` instead bars both
    directions outright (`a != k*b` and `b != k*a`), absent/false otherwise."""
    k = cast("int", params["k"])
    negate = bool(params.get("negate", False))

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        if negate:
            engine.model.add(a != k * b)
            engine.model.add(b != k * a)
            return
        s = engine.model.new_bool_var(f"{a.name}={b.name}.ratio")
        engine.model.add(a == k * b).only_enforce_if(s)
        engine.model.add(b == k * a).only_enforce_if(s.negated())

    return rel
