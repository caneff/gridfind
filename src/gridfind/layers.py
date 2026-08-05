"""The layer registry and the `board` layer.

`board` supplies the only geometry the engine knows about: a rectangular
grid of cells addressed `RxCy`, holding a single digit each. It registers
cells and emits no rules of its own (spec #4, decisions 7, 14).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, GridfindError, Layer

BOARD_SIZE = 9
MIN_DIGIT = 1
MAX_DIGIT = 9


class UnknownLayerError(GridfindError):
    """A stack names a layer the registry doesn't recognize."""


def cell_name(row: int, col: int) -> str:
    return f"R{row}C{col}"


@dataclass
class Board:
    name: str = "board"
    depends_on: tuple[str, ...] = ()

    def register(self, engine: Engine) -> None:
        grid = [
            [cell_name(row, col) for col in range(1, BOARD_SIZE + 1)]
            for row in range(1, BOARD_SIZE + 1)
        ]
        for row in grid:
            for name in row:
                engine.add_cell(name, low=MIN_DIGIT, high=MAX_DIGIT)
        engine.register_structure("grid", grid)

    def emit(self, engine: Engine) -> None:
        pass


@dataclass
class RowsDistinct:
    """The first rule-emitting layer: each row's cells are all different
    (spec #4, decision 7). Rides on `board`'s `grid` structure — it
    registers nothing new in phase 1 and only emits rules in phase 2.
    """

    name: str = "rows-distinct"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        grid = cast("list[list[str]]", engine.structures["grid"])
        for row in grid:
            engine.model.add_all_different(
                engine.cells[name].content[0] for name in row
            )


@dataclass
class LineCountDistinct:
    """somedoku's rule: row *n* holds exactly *n* distinct digits, repeats
    allowed (spec #4, decision 7 — line-count-distinct; issue #10). Rides on
    `board`'s `grid` structure exactly like `rows-distinct` — registers
    nothing new in phase 1, only emits in phase 2.
    """

    name: str = "line-count-distinct"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        grid = cast("list[list[str]]", engine.structures["grid"])
        for row_index, row in enumerate(grid, start=1):
            cells = [engine.cells[name].content[0] for name in row]
            _emit_distinct_count(
                engine, cells, target=row_index, label=f"row{row_index}"
            )


def _emit_distinct_count(
    engine: Engine, cells: list[cp_model.IntVar], *, target: int, label: str
) -> None:
    """Rule: exactly `target` distinct values appear across `cells`, repeats
    allowed — a counting rule, unlike an AllDifferent (issue #10). For each
    candidate digit, a reified "present" bool tracks whether any cell holds
    it; the digit count is the sum of those bools.
    """
    present_per_digit = []
    for digit in range(MIN_DIGIT, MAX_DIGIT + 1):
        holds_digit = []
        for i, cell in enumerate(cells):
            indicator = engine.model.new_bool_var(f"{label}.holds{digit}.{i}")
            engine.model.add(cell == digit).only_enforce_if(indicator)
            engine.model.add(cell != digit).only_enforce_if(indicator.negated())
            holds_digit.append(indicator)
        present = engine.model.new_bool_var(f"{label}.present{digit}")
        engine.model.add_max_equality(present, holds_digit)
        present_per_digit.append(present)
    engine.model.add(sum(present_per_digit) == target)


LAYER_REGISTRY = {
    "board": Board(),
    "rows-distinct": RowsDistinct(),
    "line-count-distinct": LineCountDistinct(),
}


def resolve(stack: list[str]) -> list[Layer]:
    """Resolve a stack of layer names to layer instances via the registry."""
    layers: list[Layer] = []
    for name in stack:
        layer = LAYER_REGISTRY.get(name)
        if layer is None:
            msg = f"unknown layer {name!r}"
            raise UnknownLayerError(msg)
        layers.append(layer)
    return layers
