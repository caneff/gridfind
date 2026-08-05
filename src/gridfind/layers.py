"""The layer registry and the `board` layer.

`board` supplies the only geometry the engine knows about: a rectangular
grid of cells addressed `RxCy`, holding a single digit each. It registers
cells and emits no rules of its own (spec #4, decisions 7, 14).
"""

from __future__ import annotations

from dataclasses import dataclass

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


LAYER_REGISTRY = {"board": Board()}


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
