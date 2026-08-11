"""One AllDifferent-over-groups layer, parameterized by a partition function.

`rows-distinct`, `cols-distinct`, `regions-distinct` are the same rule — every
cell in a group holds a different digit — over different groupings of the
grid. Each is a `DistinctOverGroups` instance built with a **partition
function** that reads the live grid and returns its groups; nothing is baked to
a fixed board size. That mirrors ISS's `House`-over-a-cell-set, with the cell
sets produced from board geometry rather than frozen at import
(`docs/reference/iss-design-decisions.md` §2.2, §5.3): here the geometry is the
live grid handed in via `grid_content`.

The partition functions are named for the concept they cut, not for the shape
the classic default happens to make: `regions`, not `boxes` — a jigsaw region
is no box.

The partition functions live here, local — where grid geometry queries belong
(per-layer vs. centralized) is open, so they are not centralized
ahead of that decision.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from gridfind.engine import Engine, sole
from gridfind.layers._base import emit_house, grid_content
from gridfind.layers.regions import RegionMap, region_map_for

Cell = TypeVar("Cell")
Grid = list[list[Cell]]
Partition = Callable[[Grid], Iterable[Iterable[Cell]]]


def rows(grid: Grid) -> Grid:
    return grid


def cols(grid: Grid) -> Iterable[tuple[Cell, ...]]:
    return zip(*grid, strict=True)


def _cells_for(grid: Grid, region_map: RegionMap) -> list[list[Cell]]:
    return [[grid[row - 1][col - 1] for row, col in region] for region in region_map]


def regions(grid: Grid) -> Iterable[list[Cell]]:
    """The regions, cut from whatever grid is handed in — the region partition
    reused as cell groups. `region_map_for` resolves the partition for the live
    grid's size (a 6x6 tiles as 2x3, a 4x4 as 2x2, a 9x9 as 3x3 — never four 3x3
    mini-grids on a 6x6). The refusal for a size with no classic
    box convention belongs to the resolver's fallback, not here, so it surfaces at emit
    time rather than tiling something wrong.
    """
    return _cells_for(grid, region_map_for(len(grid)))


def regions_from(region_map: RegionMap) -> Partition:
    """A partition function closed over a setter-supplied region map — the
    dispatch door's escape hatch for a jigsaw partition. Built
    fresh per puzzle at `build_stack`, never registered under a fixed name:
    the layer it feeds stays a plain `(partition)` `DistinctOverGroups`,
    never aware of where its groups came from.
    """
    return lambda grid: _cells_for(grid, region_map)


@dataclass
class DistinctOverGroups:
    """Each group in the partition holds all-different digits. The rule shared
    by rows/cols/regions-distinct; the partition is what differs.
    Rides on `board`'s `grid` structure — registers nothing, emits in phase 2.

    With no `schrodinger` layer in the stack, every cell's content stays
    width 1 and each group gets a plain `add_all_different`. With
    `schrodinger` present, `is_s` rides on the structure registry (never a
    direct reference to that layer) and each group instead gets the is_S-
    gated counting rule `emit_house` builds, over content already widened to
    length 2 by the time this runs in phase 2.
    """

    name: str
    partition: Partition
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        is_s = engine.structures.get("is_s")
        for index, group in enumerate(self.partition(grid_content(engine))):
            cells = list(group)
            if is_s is None:
                engine.model.add_all_different([sole(content) for content in cells])
            else:
                emit_house(engine, cells, label=f"{self.name}.{index}")
