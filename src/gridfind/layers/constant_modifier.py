"""The `constant` layer: the concrete `{type: constant, params: {value: k}}`
modifier. Subclasses `Modifier`, supplying only the value a discovered
constant modifier takes: a fixed integer `k`, independent of the digit
beneath it. Everything else — placement, `modifier_type` registration, the
`modifier_value` fold and its IntVar sizing — lives in the shared `Modifier`
base (ADR-0016).

`k` is the layer's own field, not read from a cage: a modifier layer places
by transversal, with no marker cages to carry a per-cell value, and `k` is a
puzzle-wide fact rather than a per-cell one. `LAYER_REGISTRY` holds the
default `ConstantModifier()` (`k = 0`, the **nullifier**); `build_stack`
builds a fresh `ConstantModifier(value=k)` for a `constant` constraint naming
its own `k`, the same fresh-param-closed-layer path `regions-distinct` uses
for `params["regions"]`.

`k` may be any integer, negative or above the digit range — `modified_bounds`
returns `(k, k)` regardless, so the fold's IntVar domain always covers the
single discovered value.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from gridfind.layers.modifier import Modifier


@dataclass
class ConstantModifier(Modifier):
    name: str = "constant"
    value: int = 0

    def value_when_modified(
        self, underlying: cp_model.LinearExprT
    ) -> cp_model.LinearExprT:
        return self.value

    def modified_bounds(self, low: int, high: int) -> tuple[int, int]:
        return self.value, self.value
