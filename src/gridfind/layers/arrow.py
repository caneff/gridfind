"""The `arrow` layer: one bulb, one or more independent shafts.

An arrow clue names a bulb (its scope, for #761, a single cell — a
multi-cell bulb, a pill read as a place-value number, is #762's follow-up)
and one or more shaft paths; each shaft's cells must sum to the bulb's own
value, each shaft checked independently — a bulb with two shafts states two
separate sum rules, not one combined total. Digits may repeat along a shaft:
only row/column/region rules forbid that, never the arrow itself (mirroring
`group-sum`'s "total only" posture).

Reads every cell — bulb and shaft alike — through `Engine.value_expr`
(ADR-0009), the one channel every value-mode layer (`group-sum`, `thermo`,
the line family's value-mode relations) already reads a cell's folded value
through: a doubler's `modifier_value`, an S-cell's combined `s_value`, or the
bare digit. The arrow layer knows nothing of modifiers or Schrödinger cells
itself.

Decode never refuses a malformed entry (`sudokumaker.arrow`); this layer
does, at emit, mirroring `equality-cage`'s own posture: an empty bulb, no
shafts, or a zero-cell shaft raises `MalformedPuzzleError` here, where the
check also covers a constraint built in memory rather than decoded off a
link. A bulb of more than one cell is #762's pill, unmodeled by this layer —
raised loud rather than read as though its lone cell were the whole bulb.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine, MalformedPuzzleError


@dataclass
class Arrow:
    """A clue whose bulb equals each of its shafts' cell-value sums,
    independently; states no distinctness of its own."""

    name: str = "arrow"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            bulb = cast("list[str]", clue.params["bulb"])
            arrows = cast("list[list[str]]", clue.params["arrows"])
            self._emit_clue(engine, bulb, arrows)

    def _emit_clue(
        self, engine: Engine, bulb: list[str], arrows: list[list[str]]
    ) -> None:
        if not bulb:
            msg = "arrow needs a bulb cell, got none"
            raise MalformedPuzzleError(msg)
        if len(bulb) > 1:
            msg = f"arrow bulb of {len(bulb)} cells (a pill) is not yet modeled — #762"
            raise MalformedPuzzleError(msg)
        if not arrows:
            msg = "arrow needs at least one shaft, got none"
            raise MalformedPuzzleError(msg)
        bulb_value = engine.value_expr(bulb[0])
        for shaft in arrows:
            if not shaft:
                msg = "arrow shaft needs at least one cell, got zero"
                raise MalformedPuzzleError(msg)
            terms = [engine.value_expr(address) for address in shaft]
            engine.model.add(sum(terms) == bulb_value)
