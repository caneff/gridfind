"""The `board` layer: the grid cells it registers.

`board` supplies the only geometry the engine knows about: a rectangular
grid of cells addressed `RxCy`, holding a single digit each. It registers
cells and emits no rules of its own (decisions 7, 14). The `RxCy` address
grid itself is `engine.cell_geometry.grid`, built once by `build_engine`
before any layer runs (ADR-0004) — this layer walks it to add and bound each
cell, rather than laying the grid out again. Size and the digit values come
from `engine.board`, the puzzle's own board shape — no module constant, so a
4x4 or 6x6 puzzle bounds its cells exactly like a 9x9 does.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine


@dataclass
class GridCells:
    """Named for the cells it registers, like its siblings are named for the
    rules they emit — and so nothing here shadows `puzzle.Board`, the setter's
    descriptor this layer reads off the engine."""

    name: str = "board"
    depends_on: tuple[str, ...] = ()

    def register(self, engine: Engine) -> None:
        board = engine.board
        for row in engine.cell_geometry.grid:
            for address in row:
                engine.add_cell(address, low=board.values.start, high=board.values[-1])
                engine.restrict(address, board.values)

    def emit(self, engine: Engine) -> None:
        pass
