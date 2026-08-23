"""The `quadruple` layer: SudokuMaker's quadruple clue (wire type `303`).

Reads value mode: each declared digit must equal at least one of the clue's
four named cells' `Engine.value_expr` (ADR-0009) — `2·d` over a doubler,
combined `s_value` over an S-cell, the bare digit otherwise — existential
presence across the 2x2 block, not placement in any particular cell. A
digit missing from every cell's value makes the clue unsatisfiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine


def _emit_quadruple_digit(
    engine: Engine, addresses: list[str], digit: int, label: str
) -> None:
    present = []
    for i, address in enumerate(addresses):
        indicator = engine.model.new_bool_var(f"{label}.{i}")
        value = engine.value_expr(address)
        engine.model.add(value == digit).only_enforce_if(indicator)
        engine.model.add(value != digit).only_enforce_if(indicator.negated())
        present.append(indicator)
    engine.model.add_bool_or(present)


@dataclass
class Quadruple:
    """SudokuMaker's quadruple clue: each declared digit must equal the
    value of at least one of the clue's four cells."""

    name: str = "quadruple"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            addresses = engine.cell_addresses(clue)
            digits = cast("list[int]", clue.params["digits"])
            for digit in digits:
                label = f"{self.name}.{addresses[0]}.{digit}"
                _emit_quadruple_digit(engine, addresses, digit, label)
