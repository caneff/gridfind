"""The `doubler` layer: the concrete `{type: doubler}` modifier. Composes
`ModifierPlacement`'s discovery and
placement unchanged — one modifier per house, a distinct-digit
transversal over `d0` — and supplies only this type's own value: a
discovered doubler doubles the value beneath it. `ModifierPlacement` itself
stays doubler-blind; this layer is the one place doubler-ness (the `2·`
coefficient) appears.

The value is carried in the model, not only reported after a solve: discovery
here is a decision variable (`is_modifier`) an arithmetic clue must react to
while the model is still being built — the demand that "a clue that only
balances if a cell is doubled forces that cell to be a doubler" needs the
CP-SAT model itself to carry the doubled value. So each cell's value is a
reified `IntVar`: the value beneath the modifier when not discovered, twice it
when discovered. That value beneath is the S-cell's combined `s_value` when the
schrödinger layer registered one for the cell, else the raw digit — so a
doubled S-cell is worth `2·s_value` (ADR-0010). It is registered under
`"modifier_value"`, a name that says nothing about doubling so a future
modifier type (a negator) can register the same channel with its own
coefficient. A layer that wants a modifier-aware value reads `"modifier_value"`
off the registry (tolerating its absence, like every other late-bound
structure) instead of the raw digit. The schrödinger layer's `"s_value"` is the
same shape for an S-cell.

Also registers `"modifier_type"` as a per-cell map naming this layer's own
cells (`"doubler"`) — the one place a discovered-modifier location can be
named, since `ModifierPlacement` itself carries no type. The map is keyed per
cell so the witness names each discovered cell from its own entry.
`Engine.modifier_types` and `verdict.py`'s witness read it back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.layers.modifier import ModifierPlacement


@dataclass
class Doubler:
    name: str = "doubler"
    depends_on: tuple[str, ...] = ("board",)
    _placement: ModifierPlacement = field(default_factory=ModifierPlacement, repr=False)

    def register(self, engine: Engine) -> None:
        # Register the value structures in phase 1, like schrodinger's
        # `s_value`, so every phase-2 reader (a killer `group-sum`, a
        # values-distinct `cage`) sees `modifier_value` no matter its own emit
        # order — a decoded link synthesizes the `doubler` constraint last, so a
        # phase-2 registration would arrive after those readers had already run.
        self._placement.register(engine)
        engine.register_structure(
            "modifier_type", dict.fromkeys(engine.cells, self.name)
        )
        is_modifier = cast(
            "dict[str, cp_model.IntVar]", engine.structures["is_modifier"]
        )
        modifier_value: dict[str, cp_model.IntVar] = {}
        for address in engine.cells:
            # Double the value beneath the modifier — the cell's `base_value`,
            # which is its combined `s_value` for an S-cell and its digit
            # otherwise. Doubling it makes a doubled S-cell worth `2·s_value`
            # and a plain doubler worth `2·d0` (ADR-0010); the seam names the
            # value beneath, so this never has to know a schrödinger layer sits
            # under it.
            underlying = engine.base_value(address)
            ceiling = 2 * max(underlying.proto.domain)
            value = engine.model.new_int_var(0, ceiling, f"{address}.modifier_value")
            engine.model.add(value == underlying).only_enforce_if(
                is_modifier[address].negated()
            )
            engine.model.add(value == 2 * underlying).only_enforce_if(
                is_modifier[address]
            )
            modifier_value[address] = value
        engine.register_structure("modifier_value", modifier_value)

    def emit(self, engine: Engine) -> None:
        self._placement.emit(engine)
