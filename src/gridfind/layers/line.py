"""The `line` layer: the shared spine every SudokuMaker line relation
(renban, whisper, palindrome, between, region-sum, sequence, grouped-line,
lockout, double-arrow) rides — one layer kind, shaped like `Thermo`, plus a
per-alias relation table.

`LINE_RELATIONS` is the one growth point: each row is `(reading_mode,
predicate)`, keyed by the clue's own `params["relation"]` alias. `emit` owns
the three family-wide decisions once — the path read, the reading-mode seam
selection, and (in a later relation) the Schrödinger digit-mode rule — so a
new relation costs one table row and one predicate, never a new layer or
decode path. Only `"value"` mode is wired so far: it reads each path cell
through `engine.value_expr` (ADR-0009, precedence `modifier_value -> s_value
-> digit`), so a doubler or a Schrödinger cell on the line counts as its
folded value, the same seam `thermo` and the pair-relation family already
read. The `"digit"` arm (`engine.real_digit_slots`, ADR-0019) is left for the
first digit-mode relation to add.

Whisper is the first row: for each adjacent path pair, `|value_expr(i) -
value_expr(i+1)| >= params["minDifference"]` — German (5) and Dutch (4) are
this same relation at a different threshold. `minDifference` is read with a
bare subscript, so a clue missing it raises `KeyError` rather than falling
back to an invented default.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.layers._base import emit_over_pairs
from gridfind.puzzle import JsonValue

ReadingMode = str  # "value" or "digit"
LinePredicate = Callable[[Engine, list[cp_model.IntVar], Mapping[str, JsonValue]], None]


def _whisper(
    engine: Engine,
    sequence: list[cp_model.IntVar],
    params: Mapping[str, JsonValue],
) -> None:
    """Every adjacent path pair's values differ by at least `minDifference`.
    Mints one fresh aux var per pair, self-named from the pair's own variable
    names (`differs_by`'s pattern) — its span covers the widest possible
    `|a - b|` read off each operand's own declared bounds, since a value_expr
    may be a doubler's `2*value` or an S-cell's `s_value`, both wider than a
    bare digit."""
    minimum = cast("int", params["minDifference"])

    def rel(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
        a_domain, b_domain = list(a.proto.domain), list(b.proto.domain)
        span = max(a_domain[-1] - b_domain[0], b_domain[-1] - a_domain[0])
        d = engine.model.new_int_var(0, span, f"{a.name}-{b.name}.gap")
        engine.model.add_abs_equality(d, a - b)
        engine.model.add(d >= minimum)

    emit_over_pairs(engine, list(pairwise(sequence)), rel)


LINE_RELATIONS: dict[str, tuple[ReadingMode, LinePredicate]] = {
    "whisper": ("value", _whisper),
}


@dataclass
class Line:
    """One line kind for every relation `LINE_RELATIONS` names, dispatched by
    each clue's own `params["relation"]` — an unrecognized alias raises
    `KeyError` (`build_stack` accepts any `line` constraint; the relation
    table is where an unmodeled alias fails loud)."""

    name: str = "line"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            relation = cast("str", clue.params["relation"])
            reading_mode, predicate = LINE_RELATIONS[relation]
            path = cast("list[str]", clue.params["path"])
            if reading_mode != "value":
                msg = (
                    f"{relation!r} line relation reads {reading_mode!r} mode, "
                    "not yet built"
                )
                raise NotImplementedError(msg)
            sequence = [
                cast("cp_model.IntVar", engine.value_expr(address)) for address in path
            ]
            predicate(engine, sequence, clue.params)
