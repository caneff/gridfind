"""The `doubler` layer: the concrete `{type: doubler}` modifier. Composes
`ModifierPlacement`'s discovery and
placement unchanged — one modifier per house, a distinct-digit
transversal over `d0` — and supplies only this type's own value fold: a
discovered doubler's value is `2·d0`. `ModifierPlacement` itself
stays doubler-blind; this layer is the one place doubler-ness (the `2·d0`
coefficient) appears.

The fold is enforced at the model level, not only reported after a solve:
`Engine.folded_value` is a post-solve read, but discovery here is a
decision variable (`is_modifier`) an arithmetic clue must react to while the
model is still being built — the demand that "a clue that only balances if a
cell is doubled forces that cell to be a doubler" needs the CP-SAT model
itself to carry the doubled value, not just report it afterwards (decision 7: "the fold
owns is_S conditionality... each consumer builds a reified expression" — generalized
here from `is_s` to `is_modifier`, the same idiom). Each cell's folded value is a
reified `IntVar`: the digit when
not discovered as the modifier, `2·digit` when it is — registered under
`"modifier_value"`, a name that says nothing about doubling so a future
modifier type (a negator) can register the same channel with its own
coefficient. An arithmetic layer that wants a modifier-aware value reads
`"modifier_value"` off the registry (tolerating its absence, like every
other late-bound structure) instead of the raw digit.

Also registers `"modifier_type"` as this layer's own name (`"doubler"`) — the
one place a discovered-modifier location can be named, since
`ModifierPlacement` itself carries no type. `Engine.modifier_type` and
`verdict.py`'s witness read it back.
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
        self._placement.register(engine)

    def emit(self, engine: Engine) -> None:
        self._placement.emit(engine)
        engine.register_structure("modifier_type", self.name)
        is_modifier = cast(
            "dict[str, cp_model.IntVar]", engine.structures["is_modifier"]
        )
        high = engine.board.values[-1]
        modifier_value: dict[str, cp_model.IntVar] = {}
        for address in engine.cells:
            d0 = engine.d0(address)
            value = engine.model.new_int_var(0, 2 * high, f"{address}.modifier_value")
            engine.model.add(value == d0).only_enforce_if(
                is_modifier[address].negated()
            )
            engine.model.add(value == 2 * d0).only_enforce_if(is_modifier[address])
            modifier_value[address] = value
        engine.register_structure("modifier_value", modifier_value)
