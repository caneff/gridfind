"""The `type 1` regions block: `regions-distinct` for an `N`x`N` board, or
nothing at all when the link carries no regions (`_regions_constraints`),
built on the matrix read (`_regions_matrix`) and the classic box tiling a
present matrix is compared against (`_classic_regions_for`).
"""

from __future__ import annotations

from gridfind.cell_geometry import BOX_SHAPE
from gridfind.layers.regions import region_map_for
from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import _enabled_blocks


def _regions_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `regions-distinct` constraint for an `N`x`N` board, or `[]` when
    the link carries no regions at all — a Latin square. Returns a list, not
    `Constraint | None`, so a `DECODER_REGISTRY` entry's handler shares the
    same shape every other decoded type's handler does.

    The region partition lives *only* in a `type 1` block. A boxed SudokuMaker
    puzzle always ships its boxes as an explicit `type 1` matrix (verified: the
    §4a classic fixture carries one), so its absence means the setter asked for
    no regions — rows and columns distinct only, no boxes invented. A present
    matrix decodes bare when it equals the board's box tiling (the engine
    supplies that partition by convention) or rides onto `params["regions"]`
    verbatim for a jigsaw. A
    `disabled: true` type-1 block is skipped — a real link may
    carry a disabled duplicate alongside the live one. Never validated here — a
    malformed matrix surfaces from `verdict`, not decode."""
    matrix = _regions_matrix(puzzle_data)
    if matrix is None:
        return []
    if size in BOX_SHAPE and matrix == _classic_regions_for(size):
        return [Constraint("regions-distinct")]
    return [Constraint("regions-distinct", params={"regions": matrix})]


def _regions_matrix(puzzle_data: dict[str, object]) -> object | None:
    """The enabled `type 1` regions matrix from the link, or `None` when the
    link carries no live jigsaw block."""
    for block in _enabled_blocks(puzzle_data, 1):
        return block.get("regions")
    return None


def _classic_regions_for(size: int) -> list[int]:
    """The standard box partition of an `N`x`N` board as SudokuMaker's flat,
    row-major region-id array — the matrix a `type 1` block equal to it is
    just the classic tiling of (no params needed)."""
    labels = [0] * (size * size)
    for region_id, box in enumerate(region_map_for(size)):
        for row, col in box:
            labels[(row - 1) * size + (col - 1)] = region_id
    return labels
