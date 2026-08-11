"""`PairRelation`: the shared engine behind every binary pair-relation layer
(#225, a prefactor for #195's `pair-ratio` and a reserved `pair-inequality`).

A pair-relation clue names two cells and holds them to some binary relation
— difference today, ratio and inequality later. One `PairRelation` instance,
built with a **relation-emitter** closure, pulls every constraint of its own
`name` via `constraints_of` and emits one rule per clue through the shared
`emit_over_pairs` walk (#42 decision 5) — exactly what `pair-difference` did
on its own before this extraction.

The relation-emitter is the seam: given a clue's own `params`, it returns
the `rel(engine, a, b)` callable `emit_over_pairs` applies to the pair. Each
relation owns its own params key and rule shape behind that one closure —
`PairRelation` itself never reads a relation-specific key (a difference
clue's `diff`, a future ratio clue's own key), so a new relation costs one
registry row plus one emitter function, not a change here.

Sum stays out of this family: it is an N-ary group reduction (`pair-sum`,
`cage`), not a binary relation (spec #195).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.layers._base import emit_over_pairs
from gridfind.puzzle import JsonValue

RelationEmitter = Callable[
    [Mapping[str, JsonValue]],
    Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None],
]


@dataclass
class PairRelation:
    name: str
    relation: RelationEmitter
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — cells is the one
            # key every pair relation shares; the rest is the emitter's own.
            addresses = cast("list[str]", clue.params["cells"])
            a, b = (engine.content(address) for address in addresses)
            emit_over_pairs(engine, [(a, b)], self.relation(clue.params))
