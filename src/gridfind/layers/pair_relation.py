"""`PairRelation`: the shared engine behind every binary pair-relation layer
(a prefactor for `pair-ratio`).

A pair-relation clue names two cells and holds them to some binary relation
— difference today, ratio and inequality later. One `PairRelation` instance,
built with a **relation-emitter** closure, pulls every constraint of its own
`name` via `constraints_of` and applies the relation directly to its own two
cells — a pair is not a many-cell walk, so it costs no walk of its own
(`thermo`'s consecutive-pair decomposition is the many-cell case; it keeps
the shared `emit_over_pairs` walk in `_base.py`).

The relation-emitter is the seam: given a clue's own `params`, it returns
the `rel(engine, a, b)` callable this layer calls directly on the pair. Each
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
from gridfind.puzzle import JsonValue

RelationEmitter = Callable[
    [Mapping[str, JsonValue]],
    Callable[[Engine, cp_model.IntVar, cp_model.IntVar], None],
]


@dataclass
class PairRelation:
    """Reads each pair's cells through `engine.value_expr` (ADR-0009), the
    same seam `group-sum` and a values-distinct `cage` already read: a plain
    digit, a doubler's `2·value`, or an S-cell's combined `s_value` (no
    per-candidate rule). No `s_blind` flag — unlike `offset_adjacency`, this
    family never reads a cell's raw content slot, so it composes freely with
    a widening (Schrödinger) layer."""

    name: str
    relation: RelationEmitter
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # cells is the one key every pair relation shares; the rest is
            # the emitter's own.
            addresses = engine.cell_addresses(clue)
            if len(addresses) != 2:
                msg = (
                    f"{self.name!r} names a pair — expected 2 cells, "
                    f"got {len(addresses)}"
                )
                raise MalformedPuzzleError(msg)
            # value_expr always reifies an actual solver variable (a plain
            # cell's content, a doubler's modifier_value, an S-cell's
            # s_value) rather than a compound expression, so the relation
            # emitters — which name their own aux vars off a/b — narrow back
            # to IntVar, same as engine.content.
            a, b = (
                cast("cp_model.IntVar", engine.value_expr(address))
                for address in addresses
            )
            self.relation(clue.params)(engine, a, b)
