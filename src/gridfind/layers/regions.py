"""The `regions-distinct` layer and its region-partition maps.

The region maps live here, not in `_base`: they are used only by this layer,
so they are region-specific, not shared infrastructure (issue #17).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gridfind.engine import Engine
from gridfind.layers._base import grid_vars
from gridfind.layers.board import BOARD_SIZE

REGION_SIZE = 3


def classic_region_map(
    board_size: int = BOARD_SIZE, region_size: int = REGION_SIZE
) -> list[list[tuple[int, int]]]:
    """The classic 3x3-box partition of a 9x9 board (spec #4, decision 7):
    row/col bands of `region_size` cells, read left-to-right, top-to-bottom.
    """
    bands = board_size // region_size
    return [
        [
            (band_row * region_size + r, band_col * region_size + c)
            for r in range(1, region_size + 1)
            for c in range(1, region_size + 1)
        ]
        for band_row in range(bands)
        for band_col in range(bands)
    ]


def _irregular_demo_region_map() -> list[list[tuple[int, int]]]:
    """A jigsaw partition proving `regions-distinct` needs no new layer for
    irregular sudoku (issue #8): the classic 3x3 boxes with one cell swapped
    between two adjacent boxes, so neither region is a square anymore.

    Not every such swap keeps the partition solvable alongside rows/cols
    distinct — a partition into 9 cell-groups of 9 only admits a completion
    for specific (gerechte-design) choices. This swap (R1C3 <-> R2C4) was
    checked against `verdict` with an empty working state before being
    hardcoded here; it is confirmed satisfiable.
    """
    regions = classic_region_map()
    regions[0] = [cell for cell in regions[0] if cell != (1, 3)]
    regions[0].append((2, 4))
    regions[1] = [cell for cell in regions[1] if cell != (2, 4)]
    regions[1].append((1, 3))
    return regions


@dataclass
class RegionsDistinct:
    """Each region's cells are all different, where a region is a
    caller-supplied partition of the grid (spec #4, decision 7; issue #8).
    Parameterized by `region_map`: the classic 3x3-box default gives classic
    sudoku, any other partition gives irregular sudoku through this same
    layer. Rides on `board`'s `grid` structure like rows/cols-distinct —
    registers nothing new in phase 1, only emits rules in phase 2.
    """

    name: str = "regions-distinct"
    depends_on: tuple[str, ...] = ("board",)
    region_map: list[list[tuple[int, int]]] = field(default_factory=classic_region_map)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        grid = grid_vars(engine)
        for region in self.region_map:
            engine.model.add_all_different(
                grid[row - 1][col - 1] for row, col in region
            )
