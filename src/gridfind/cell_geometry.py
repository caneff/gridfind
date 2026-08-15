"""`CellGeometry`: the typed home for a board's fixed facts (ADR-0004).

The board size, the digit values, the box tiling, and the grid of `RxCy`
addresses answer to no layer's work — any code holding the board could
compute the identical facts. `cell_geometry(board)` builds the descriptor
once from a `Board`; `build_engine` attaches it to the engine so every layer
reads it off `engine.cell_geometry`, and `sudokumaker`, which has no engine,
builds its own straight from the board it holds. Metadata only: no content,
no solver state (ADR-0004 decision 2).

A leaf module on purpose: nothing here imports `gridfind.engine` or any
layer, so `engine.py` and `layers/regions.py` can both import this module
without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# N -> (box_rows, box_cols): the classic box convention a board of this size
# tiles by — a 6x6 as six 2x3 boxes, a 4x4 as four 2x2, a 9x9 as nine 3x3,
# never a 6x6 as four 3x3 mini-grids. A size absent here has no classic box
# convention: `cell_geometry` leaves `box_shape` `None` rather than guessing
# one, and `layers.regions.region_map_for` refuses a bare `regions-distinct`
# at that size on the same table.
BOX_SHAPE: dict[int, tuple[int, int]] = {4: (2, 2), 6: (2, 3), 9: (3, 3)}


class BoardShape(Protocol):
    """A puzzle's board shape facts — size and digit values, `cell_geometry`'s
    only input. The read-only view both `engine.py`'s `Engine.board` and
    `sudokumaker`'s own `Board` satisfy, so this module never imports the
    concrete `Board` type behind either."""

    @property
    def size(self) -> int: ...

    @property
    def values(self) -> range: ...


def cell_address(row: int, col: int) -> str:
    """The wire address of a 1-based grid cell: row 3, col 1 is `R3C1`."""
    return f"R{row}C{col}"


@dataclass(frozen=True)
class CellGeometry:
    """The puzzle's cell space: the fixed facts every reader wants typed
    back instead of fished out with a cast (ADR-0004 decision 2).

    Named for the cell space it describes, not for any one cell — gridfind
    has a real `Cell` class, and off-grid cells are coming (#399), so
    `GridGeometry` would name a subset once they land.

    `box_shape` is `None` for a board size with no classic box convention —
    the board still supports rows/cols-distinct alone, no boxes invented.
    `grid` lays out every cell's `RxCy` address row-major.
    """

    size: int
    values: range
    box_shape: tuple[int, int] | None
    grid: list[list[str]]


def cell_geometry(board: BoardShape) -> CellGeometry:
    """Build the descriptor from a board's fixed facts (ADR-0004 decision 3)
    — the one place that lays out the `RxCy` address grid from `board.size`.
    Every other reader takes the built `CellGeometry` instead of repeating
    this walk."""
    grid = [
        [cell_address(row, col) for col in range(1, board.size + 1)]
        for row in range(1, board.size + 1)
    ]
    return CellGeometry(
        size=board.size,
        values=board.values,
        box_shape=BOX_SHAPE.get(board.size),
        grid=grid,
    )
