"""The region-partition map for `regions-distinct`.

The 3x3-box partition lives here, not in `_base`: it is region-specific, not
shared infrastructure (issue #17). The `regions-distinct` rule itself is one
instance of the shared `DistinctOverGroups` layer (issue #37), whose `boxes`
partition maps this address partition onto the live grid.
"""

from __future__ import annotations

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
