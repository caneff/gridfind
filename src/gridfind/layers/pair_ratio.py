"""The `pair-ratio` relation: black kropki (spec #195, issue #226), the
third explicit-pair variant expressed as a `PairRelation` (issue #225)
relation-emitter.

A pair-ratio clue names two cells whose contents stand in a fixed integer
ratio `k`, undirected — either cell may hold the larger value. `ratio_of` is
the relation-emitter `LAYER_REGISTRY["pair-ratio"]` builds its `PairRelation`
with: given a clue's params, it reads the target `k` and returns the `rel`
that pins one pair to it.

`k` is a constant, so both `a == k*b` and `b == k*a` are linear — no
`add_multiplication_equality` needed. The undirected either-or is one
reified bool, mirroring the `schrodinger` layer's precedent
(`only_enforce_if(s)` / `only_enforce_if(s.negated())`) rather than a
hand-built disjunction or a truth table.

Deliberately narrow, mirroring `pair-difference`: a **pair**, not a
**domino** — the relation never asks whether the cells are adjacent (that
geometry is #43) — and positive-only, carrying no implied distinctness (that
is `cage`'s job). A `k == 1` clue forces `a == b`, which resolves `broke`
under distinctness as a natural consequence of the rest of the stack, not a
case special-cased here.
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
    per pair, self-named from the pair's own variable names since
    `emit_over_pairs` carries no label, and pins `a == k*b` under `s`,
    `b == k*a` under its negation — undirected, either cell may hold the
    larger value."""
    k = cast("int", params["k"])

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        s = engine.model.new_bool_var(f"{a.name}={b.name}.ratio")
        engine.model.add(a == k * b).only_enforce_if(s)
        engine.model.add(b == k * a).only_enforce_if(s.negated())

    return rel
