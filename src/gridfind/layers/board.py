"""The `board` layer and the grid geometry it owns.

`board` supplies the only geometry the engine knows about: a rectangular
grid of cells addressed `RxCy`, holding a single digit each. It registers
cells and emits no rules of its own (spec #4, decisions 7, 14). The core
holds zero geometry — `cell_address` travels with the layer that supplies it,
so a future hex board stays clean (issue #17). Size and the digit values
come from `engine.board`, the puzzle's own board shape (issue #77) — no
module constant, so a 4x4 or 6x6 puzzle sizes its grid and cell bounds
exactly like a 9x9 does.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine


def cell_address(row: int, col: int) -> str:
    return f"R{row}C{col}"


@dataclass
class GridCells:
    """Named for the cells it registers, like its siblings are named for the
    rules they emit — and so nothing here shadows `puzzle.Board`, the setter's
    descriptor this layer reads off the engine (issue #91)."""

    name: str = "board"
    depends_on: tuple[str, ...] = ()

    def register(self, engine: Engine) -> None:
        board = engine.board
        grid = [
            [cell_address(row, col) for col in range(1, board.size + 1)]
            for row in range(1, board.size + 1)
        ]
        for row in grid:
            for address in row:
                engine.add_cell(address, low=board.values.start, high=board.values[-1])
                engine.restrict(address, board.values)
        engine.register_structure("grid", grid)

    def emit(self, engine: Engine) -> None:
        pass
