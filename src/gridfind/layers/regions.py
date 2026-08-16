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

`region_map_from_labels` reads the setter-supplied shape: a
setter's `regions-distinct` constraint carries `params["regions"]` as a flat,
row-major array of one integer label per cell — SudokuMaker's own jigsaw wire
shape, not a `RegionMap`. It converts and validates in one step: the matrix
shape makes a gap or overlap unexpressible, so there is nothing to check
beyond length and entry type. An over-large region (more cells than the
digit domain) is not this function's concern — that is a satisfiability fact
the solver reports as broke, never a validator's judgment.

`region_map_for_constraints` is the one door onto a whole
constraint list rather than a single already-found constraint: it scans for
`regions-distinct` and picks jigsaw (`region_map_from_labels`) vs. box tiling
(`region_map_for`), but also owns the third case neither of the above two
decide alone — no `regions-distinct` constraint at all, which resolves to one
region covering the whole board. `build_stack`, the witness render path, and
`witness_validator` all cross this one seam instead of each re-deriving
the same three-way branch, which is what let them quietly resolve
different partitions.

`reason` is the broke-verdict diagnosis living beside the
region layers it reasons about, rather than inside `verdict.py`'s
found/broke/unknown classifier: it asks this module's own
`region_map_for_constraints` door, the same one `verdict.py` and
`witness_validator.py` cross.
"""

from __future__ import annotations

from collections.abc import Iterable

from gridfind.cell_geometry import BOX_SHAPE
from gridfind.engine import GridfindError, MalformedPuzzleError
from gridfind.layers import door
from gridfind.puzzle import Constraint, Puzzle

# A partition of a board into regions of cell addresses, whatever its source.
RegionMap = list[list[tuple[int, int]]]


def box_regions(size: int, box_rows: int, box_cols: int) -> RegionMap:
    """The box partition of a `size`x`size` board tiled by `box_rows` x
    `box_cols` boxes: row/col bands read left-to-right,
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


def region_map_for(size: int) -> RegionMap:
    """The region map a `size`x`size` board tiles by convention — the
    `BOX_SHAPE` table by size. A setter's own jigsaw map goes through
    `region_map_from_labels` instead; this door only resolves the classic
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


def region_map_from_labels(size: int, labels: object) -> RegionMap:
    """Convert a setter's flat, row-major label array into a `RegionMap`,
    grouping cells by label — ids need not be contiguous, and group sizes
    need not be equal. Anything other than exactly `size**2`
    integer entries is not this shape at all, so it raises
    `MalformedPuzzleError` rather than being coerced.
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
                return region_map_from_labels(size, constraint.params["regions"])
            return region_map_for(size)
    return [[(row, col) for row in range(1, size + 1) for col in range(1, size + 1)]]


def reason(puzzle: Puzzle) -> str | None:
    """The broke witness's region-blame: the first region in the resolved partition
    outside the feasibility band `cells <= domain <= 2*cells`, named by its 1-based
    position and cell count against the
    domain size. Two symmetric violations:

    - **Over-sized** (`cells > domain`): a forced repeat by
      pigeonhole. Holds regardless of Schrodinger widening — a region's
      `d0` slots alone already outnumber the domain.
    - **Under-coverable** (`domain > 2*cells`): too few slots
      to cover the domain even with every cell doubled up as an S-cell.
      Only a real cause of infeasibility when `schrodinger` is in play — a
      region with no cover pressure just forbids repeats, and `domain >
      2*cells` alone never breaks that.

    Only checked when a regions-distinct constraint is actually in play, so
    a puzzle with no such rule (or an ordinary contradiction with every
    region in bounds) carries no message. Expands `puzzle.constraints` itself
    (a `sudoku` preset carries `regions-distinct` indirectly) rather than
    asking a caller to hand in the already-expanded list, the one door onto
    the region map (`region_map_for_constraints`)."""
    canonical = door.expand_constraints(puzzle.constraints)
    if not any(constraint.type == "regions-distinct" for constraint in canonical):
        return None
    region_map = region_map_for_constraints(canonical, puzzle.board.size)
    domain_size = len(puzzle.board.values)
    has_schrodinger = any(constraint.type == "schrodinger" for constraint in canonical)
    for index, region in enumerate(region_map, start=1):
        cells = len(region)
        if cells > domain_size:
            return f"region {index} holds {cells} cells, domain is {domain_size}"
        if has_schrodinger and domain_size > 2 * cells:
            return (
                f"region {index} holds {cells} cells, domain is {domain_size} "
                "— too few to cover"
            )
    return None
