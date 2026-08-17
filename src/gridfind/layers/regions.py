"""The region-partition map for `regions-distinct`.

One word each way: **region** is the concept, **box** is the classic default
that fills it. So the general names here say region and the tiling generators
say box — a jigsaw region is not a box.

The box partition lives here, not in `_base`: it is region-specific, not
shared infrastructure. The `regions-distinct` rule itself is one
instance of the shared `DistinctOverGroups` layer, whose `regions`
partition maps this address partition onto the live grid.

`BOX_SHAPE`, the convention that gives a board its box shape (a 6x6 tiles as
six 2x3 boxes, a 4x4 as four 2x2, a 9x9 as nine 3x3 — never a 6x6 as four 3x3
mini-grids), lives on `CellGeometry` (ADR-0004): `cell_geometry.BOX_SHAPE`
is the one table, and `CellGeometry.box_shape` is a board's own resolved
entry from it. `box_regions` is the one tiling generator, here because it is
region-specific, not shared infrastructure.

`region_map_for` is the one door onto the classic box tiling: the table
lookup by size.

`RegionMap.from_labels` reads the setter-supplied shape: a
setter's `regions-distinct` constraint carries `params["regions"]` as a flat,
row-major array of one integer label per cell — SudokuMaker's own jigsaw wire
shape, not a `RegionMap`. It converts and validates in one step: the matrix
shape makes a gap or overlap unexpressible, so there is nothing to check
beyond length and entry type. An over-large region (more cells than the
digit domain) is not this method's concern — that is a satisfiability fact
the solver reports as broke, never a validator's judgment.

`region_map_for_constraints` is the one door onto a whole
constraint list rather than a single already-found constraint: it scans for
`regions-distinct` and picks jigsaw (`RegionMap.from_labels`) vs. box tiling
(`region_map_for`), but also owns the third case neither of the above two
decide alone — no `regions-distinct` constraint at all, which resolves to one
region covering the whole board. `build_stack`, the witness render path, and
`witness_validator` all cross this one seam instead of each re-deriving
the same three-way branch, which is what let them quietly resolve
different partitions.
"""

from __future__ import annotations

from collections.abc import Iterable

from gridfind.cell_geometry import BOX_SHAPE, flat_index
from gridfind.engine import GridfindError, MalformedPuzzleError
from gridfind.puzzle import Constraint


class RegionMap(list[list[tuple[int, int]]]):
    """A partition of a board into regions of cell addresses, whatever its
    source — each element is one region's list of `(row, col)` addresses.
    A `list` subclass rather than a bare alias so the wire-label codec
    (`to_labels`/`from_labels`) has a named home.
    """

    def to_labels(self, size: int) -> list[int]:
        """This region map as SudokuMaker's flat, row-major `type 1` array: entry
        `(row - 1) * size + (col - 1)` is the number of the region holding cell
        `RxCy`. The one home for serializing a `RegionMap` to the wire form,
        shared by the decode-time classic-tiling check and the corpus synthesizers.
        """
        region_numbers = [0] * (size * size)
        for number, region in enumerate(self):
            for row, col in region:
                region_numbers[(row - 1) * size + (col - 1)] = number
        return region_numbers

    @classmethod
    def from_labels(cls, size: int, labels: object) -> RegionMap:
        """Convert a setter's flat, row-major label array into a `RegionMap`,
        grouping cells by label — ids need not be contiguous, and group sizes
        need not be equal. Anything other than exactly `size**2`
        integer entries is not this shape at all, so it raises
        `MalformedPuzzleError` rather than being coerced. Round-trips with
        `to_labels` up to relabeling: group membership survives, not the
        original label values or region order.
        """
        if not isinstance(labels, list) or len(labels) != size * size:
            msg = f"regions must be a list of {size * size} labels, got {labels!r}"
            raise MalformedPuzzleError(msg)
        groups: dict[int, list[tuple[int, int]]] = {}
        for index, label in enumerate(labels):
            if not isinstance(label, int):
                msg = f"region label must be an int, got {label!r}"
                raise MalformedPuzzleError(msg)
            row, col = divmod(index, size)
            groups.setdefault(label, []).append((row + 1, col + 1))
        return cls(groups.values())


def box_regions(size: int, box_rows: int, box_cols: int) -> RegionMap:
    """The box partition of a `size`x`size` board tiled by `box_rows` x
    `box_cols` boxes: row/col bands read left-to-right,
    top-to-bottom. The one box-tiling generator — `box_regions(9, 3, 3)` is
    the classic 3x3 partition, no separate 9x9-only formula needed.
    """
    row_bands = size // box_rows
    col_bands = size // box_cols
    return RegionMap(
        [
            (band_row * box_rows + r, band_col * box_cols + c)
            for r in range(1, box_rows + 1)
            for c in range(1, box_cols + 1)
        ]
        for band_row in range(row_bands)
        for band_col in range(col_bands)
    )


def to_region_numbers(size: int, region_map: RegionMap) -> list[int]:
    """A region map as SudokuMaker's flat, row-major `type 1` array: entry
    `flat_index(row, col, size)` is the number of the region holding cell
    `RxCy`. The one home for serializing a `RegionMap` to the wire form,
    shared by the decode-time classic-tiling check and the corpus synthesizers.
    """
    region_numbers = [0] * (size * size)
    for number, region in enumerate(region_map):
        for row, col in region:
            region_numbers[flat_index(row, col, size)] = number
    return region_numbers


def region_map_for(size: int) -> RegionMap:
    """The region map a `size`x`size` board tiles by convention — the
    `BOX_SHAPE` table by size. A setter's own jigsaw map goes through
    `RegionMap.from_labels` instead; this door only resolves the classic
    box tiling.

    The refusal sits here, on the fallback, not on the consumer: only a board
    asking to be tiled by convention needs a convention to exist, so a 5x5
    carrying its own region map is perfectly legal.
    """
    resolved = BOX_SHAPE.get(size)
    if resolved is None:
        msg = f"no classic box convention for a {size}x{size} board"
        raise GridfindError(msg)
    return box_regions(size, *resolved)


def region_map_for_constraints(
    constraints: Iterable[Constraint], size: int
) -> RegionMap:
    """The region map a `size`x`size` board's own constraints imply: the setter's jigsaw
    matrix when the `regions-distinct` constraint
    carries `params["regions"]`, the board's box tiling by convention when
    it's bare, or one region covering the whole board when no
    `regions-distinct` constraint is present — a Latin square draws no
    interior lines the solver never enforced. The one door callers cross
    instead of each re-deriving this same three-way branch.
    """
    for constraint in constraints:
        if constraint.type == "regions-distinct":
            if "regions" in constraint.params:
                return RegionMap.from_labels(size, constraint.params["regions"])
            return region_map_for(size)
    return RegionMap(
        [[(row, col) for row in range(1, size + 1) for col in range(1, size + 1)]]
    )
