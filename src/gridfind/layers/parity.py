"""The `parity` layer: SudokuMaker's even/odd cell clue (wire types
`100`/`101`).

Reads value mode: each named cell's `Engine.value_expr` (ADR-0009) — `2·d`
over a doubler, combined `s_value` over an S-cell, the bare digit
otherwise — is forced to the clue's declared parity.
An odd clue over a doubled cell is therefore unsatisfiable (`2·d` is never
odd), and an even clue over one is trivially met — the value reading,
chosen deliberately over reading the raw placed digit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine

_REMAINDER = {"even": 0, "odd": 1}


def _emit_parity_cell(engine: Engine, address: str, parity: str) -> None:
    value = engine.value_expr(address)
    remainder = engine.model.new_int_var(0, 1, f"parity.{address}.remainder")
    engine.model.add_modulo_equality(remainder, value, 2)
    engine.model.add(remainder == _REMAINDER[parity])


@dataclass
class Parity:
    """SudokuMaker's even/odd clue: each named cell's value must hold the
    clue's declared parity."""

    name: str = "parity"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            parity = cast("str", clue.params["parity"])
            for address in engine.cell_addresses(clue):
                _emit_parity_cell(engine, address, parity)
