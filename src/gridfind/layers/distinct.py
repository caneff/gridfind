"""One AllDifferent-over-groups layer, parameterized by a partition function.

`rows-distinct`, `cols-distinct`, `regions-distinct` are the same rule — every
cell in a group holds a different digit — over different groupings of the grid
(issue #37). Each is a `DistinctOverGroups` instance built with a **partition
function** that reads the live grid and returns its groups; nothing is baked to
a fixed board size. That mirrors ISS's `House`-over-a-cell-set, with the cell
sets produced from board geometry rather than frozen at import
(`docs/reference/iss-design-decisions.md` §2.2, §5.3): here the geometry is the
live grid handed in via `grid_vars`.

The partition functions live here, local — where grid geometry queries belong
(per-layer vs. centralized) is open (issue #43), so they are not centralized
ahead of that decision.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from gridfind.engine import Engine
from gridfind.layers._base import grid_vars
from gridfind.layers.regions import classic_region_map

Cell = TypeVar("Cell")
Grid = list[list[Cell]]
Partition = Callable[[Grid], Iterable[Iterable[Cell]]]


def rows(grid: Grid) -> Grid:
    return grid


def cols(grid: Grid) -> Iterable[tuple[Cell, ...]]:
    return zip(*grid, strict=True)


def boxes(grid: Grid) -> Iterable[list[Cell]]:
    """The classic 3x3 boxes, cut from whatever grid is handed in — the region
    partition reused as cell groups. `classic_region_map` gives the boxes as
    1-indexed (row, col) addresses for the actual board size; map each onto the
    live grid so `regions-distinct` stays size-agnostic like rows/cols.
    """
    return [
        [grid[row - 1][col - 1] for row, col in region]
        for region in classic_region_map(len(grid))
    ]


@dataclass
class DistinctOverGroups:
    """Each group in the partition holds all-different digits. The rule shared
    by rows/cols/regions-distinct (issue #37); the partition is what differs.
    Rides on `board`'s `grid` structure — registers nothing, emits in phase 2.
    """

    name: str
    partition: Partition
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for group in self.partition(grid_vars(engine)):
            engine.model.add_all_different(group)
