"""The layer registry and the `board` layer.

`board` supplies the only geometry the engine knows about: a rectangular
grid of cells addressed `RxCy`, holding a single digit each. It registers
cells and emits no rules of its own (spec #4, decisions 7, 14).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

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


LAYER_REGISTRY = {"board": Board(), "rows-distinct": RowsDistinct()}


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
