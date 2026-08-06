"""The `board` layer and the grid geometry it owns.

`board` supplies the only geometry the engine knows about: a rectangular
grid of cells addressed `RxCy`, holding a single digit each. It registers
cells and emits no rules of its own (spec #4, decisions 7, 14). The core
holds zero geometry — `cell_name` and `BOARD_SIZE` travel with the layer
that supplies them, so a future hex board stays clean (issue #17).
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine
from gridfind.layers._base import MAX_DIGIT, MIN_DIGIT

BOARD_SIZE = 9


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
