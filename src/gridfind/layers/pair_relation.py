"""`PairRelation`: the shared engine behind every binary pair-relation layer
(a prefactor for `pair-ratio` and a reserved `pair-inequality`).

A pair-relation clue names two cells and holds them to some binary relation
— difference today, ratio and inequality later. One `PairRelation` instance,
built with a **relation-emitter** closure, pulls every constraint of its own
`name` via `constraints_of` and emits one rule per clue through the shared
`emit_over_pairs` walk (decision 5).

The relation-emitter is the seam: given a clue's own `params`, it returns
the `rel(engine, a, b)` callable `emit_over_pairs` applies to the pair. Each
relation owns its own params key and rule shape behind that one closure —
`PairRelation` itself never reads a relation-specific key (a difference
clue's `diff`, a future ratio clue's own key), so a new relation costs one
registry row plus one emitter function, not a change here.

Sum stays out of this family: it is an N-ary group reduction (`group-sum`,
`cage`), not a binary relation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, MalformedPuzzleError
from gridfind.layers._base import emit_over_pairs
from gridfind.puzzle import JsonValue

RelationEmitter = Callable[
    [Mapping[str, JsonValue]],
    Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None],
]


@dataclass
class PairRelation:
    """`s_blind`: reads a cell through `engine.content`, its single slot —
    undefined once a widening layer gives a cell a second slot (`build_stack`
    refuses the combination)."""

    name: str
    relation: RelationEmitter
    depends_on: tuple[str, ...] = ("board",)
    s_blind: bool = True

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — cells is the one
            # key every pair relation shares; the rest is the emitter's own.
            addresses = cast("list[str]", clue.params["cells"])
            if len(addresses) != 2:
                msg = (
                    f"{self.name!r} names a pair — expected 2 cells, "
                    f"got {len(addresses)}"
                )
                raise MalformedPuzzleError(msg)
            a, b = (engine.content(address) for address in addresses)
            emit_over_pairs(engine, [(a, b)], self.relation(clue.params))
