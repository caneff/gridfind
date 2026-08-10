"""The region-partition map for `regions-distinct`.

One word each way: **region** is the concept, **box** is the classic default
that fills it. So the general names here say region and the tiling generators
say box — a jigsaw region is not a box, which is what #30 will prove.

The box partition lives here, not in `_base`: it is region-specific, not
shared infrastructure (issue #17). The `regions-distinct` rule itself is one
instance of the shared `DistinctOverGroups` layer (issue #37), whose `regions`
partition maps this address partition onto the live grid.

`BOX_SHAPE` (issue #77) is the convention that gives a board its box shape:
a 6x6 tiles as six 2x3 boxes, a 4x4 as four 2x2, a 9x9 as nine 3x3 — never a
6x6 as four 3x3 mini-grids (the *quattro quadri* the old single-board-size
partition produced). `box_regions` is the one generator: it serves every
board size, including the classic 9x9 the SudokuMaker decoder reads through
`region_map_for` (issue #105).

`region_map_for` is the one door onto all of it (issue #79 ruling): the
setter's own map when given, the box tiling by convention when not. The
table itself, `BOX_SHAPE`, also feeds the witness's own render (issue #105) —
the verdict reads it when it builds a witness, so the box shape travels with
the grid rather than being re-derived by whoever prints it.

`region_map_from_labels` (issue #123) reads the other supplied shape: a
setter's `regions-distinct` constraint carries `params["regions"]` as a flat,
row-major array of one integer label per cell — SudokuMaker's own jigsaw wire
shape, not a `RegionMap`. It converts and validates in one step: the matrix
shape makes a gap or overlap unexpressible, so there is nothing to check
beyond length and entry type. An over-large region (more cells than the
digit domain) is not this function's concern — that is a satisfiability fact
the solver reports as broke, never a validator's judgment.

`region_map_for_constraints` (issue #207) is the one door onto a whole
constraint list rather than a single already-found constraint: it scans for
`regions-distinct` and picks jigsaw vs. box tiling exactly as `region_map_for`
would, but also owns the third case neither of the above two decide alone —
no `regions-distinct` constraint at all, which resolves to one region
covering the whole board. `build_stack`, the witness render path, and
`witness_validator` all cross this one seam instead of each re-deriving
the same three-way branch, which is what let them quietly resolve
different partitions.
"""

from __future__ import annotations

from collections.abc import Iterable

from gridfind.engine import GridfindError, MalformedPuzzleError
from gridfind.puzzle import Constraint

# A partition of a board into regions of cell addresses, whatever its source.
RegionMap = list[list[tuple[int, int]]]

# N -> (box_rows, box_cols): the classic box convention this board size tiles
# by. A size absent here has no classic box convention (issue #77) —
# `region_map_for` refuses rather than guessing one.
BOX_SHAPE: dict[int, tuple[int, int]] = {4: (2, 2), 6: (2, 3), 9: (3, 3)}


def box_regions(size: int, box_rows: int, box_cols: int) -> RegionMap:
    """The box partition of a `size`x`size` board tiled by `box_rows` x
    `box_cols` boxes (issue #77): row/col bands read left-to-right,
    top-to-bottom. The one box-tiling generator — `box_regions(9, 3, 3)` is
    the classic 3x3 partition, no separate 9x9-only formula needed.
    """
    row_bands = size // box_rows
    col_bands = size // box_cols
    return [
        [
            (band_row * box_rows + r, band_col * box_cols + c)
            for r in range(1, box_rows + 1)
            for c in range(1, box_cols + 1)
        ]
        for band_row in range(row_bands)
        for band_col in range(col_bands)
    ]


def region_map_for(size: int, supplied: RegionMap | None = None) -> RegionMap:
    """The region map a `size`x`size` board runs on: the setter's own map when
    given, the board's box tiling by convention when not (issue #79 ruling).
    One consumer, one shape, two sources — a setter-supplied map (#30) is not
    a second path beside the box tiling, it supplies what the tiling would
    otherwise compute.

    The refusal sits here, on the fallback, not on the consumer: only a board
    asking to be tiled by convention needs a convention to exist, so a 5x5
    carrying its own region map is perfectly legal.
    """
    if supplied is not None:
        return supplied
    if size not in BOX_SHAPE:
        msg = f"no classic box convention for a {size}x{size} board"
        raise GridfindError(msg)
    return box_regions(size, *BOX_SHAPE[size])


def region_map_from_labels(size: int, labels: object) -> RegionMap:
    """Convert a setter's flat, row-major label array into a `RegionMap`,
    grouping cells by label — ids need not be contiguous, and group sizes
    need not be equal (issue #123). Anything other than exactly `size**2`
    integer entries is not this shape at all, so it raises
    `MalformedPuzzleError` (the #107 convergence) rather than being coerced.
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
    return list(groups.values())


def region_map_for_constraints(
    constraints: Iterable[Constraint], size: int
) -> RegionMap:
    """The region map a `size`x`size` board's own constraints imply (issue
    #207): the setter's jigsaw matrix when the `regions-distinct` constraint
    carries `params["regions"]`, the board's box tiling by convention when
    it's bare, or one region covering the whole board when no
    `regions-distinct` constraint is present — a Latin square draws no
    interior lines the solver never enforced. The one door callers cross
    instead of each re-deriving this same three-way branch.
    """
    for constraint in constraints:
        if constraint.type == "regions-distinct":
            if "regions" in constraint.params:
                return region_map_from_labels(size, constraint.params["regions"])
            return region_map_for(size)
    return [[(row, col) for row in range(1, size + 1) for col in range(1, size + 1)]]
