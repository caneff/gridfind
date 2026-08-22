"""The `doubler` layer: the concrete `{type: doubler}` modifier. Subclasses
`Modifier`, supplying only the value a discovered doubler takes: twice the
value beneath it. Everything else — placement, `modifier_type` registration,
the `modifier_value` fold and its IntVar sizing — lives in the shared
`Modifier` base (ADR-0016).

The value is carried in the model, not only reported after a solve: discovery
is a decision variable (`is_modifier`) an arithmetic clue must react to while
the model is still being built — the demand that "a clue that only balances
if a cell is doubled forces that cell to be a doubler" needs the CP-SAT model
itself to carry the doubled value. The value beneath is the S-cell's combined
`s_value` when the schrödinger layer registered one for the cell, else the
raw digit (`Modifier.register` reads it via `engine.base_value`) — so a
doubled S-cell is worth `2·s_value` (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from gridfind.layers.modifier import Modifier


@dataclass
class Doubler(Modifier):
    """A discovered modifier whose value, when placed, folds to twice the
    digit (or S-cell value) beneath it."""

    name: str = "doubler"

    def value_when_modified(
        self, underlying: cp_model.LinearExprT
    ) -> cp_model.LinearExprT:
        return 2 * underlying

    def modified_bounds(self, low: int, high: int) -> tuple[int, int]:
        return 2 * low, 2 * high
