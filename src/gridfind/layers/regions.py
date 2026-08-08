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
partition produced). `box_regions` generalizes `classic_boxes` to
any of these; `classic_boxes` stays as the 9x9-only convenience the
SudokuMaker decoder (classic-only, #59) reads.

`region_map_for` is the one door onto all of it (issue #79 ruling): the
setter's own map when given, the box tiling by convention when not.
"""

from __future__ import annotations

from gridfind.engine import GridfindError

BOX_SIZE = 3

# A partition of a board into regions of cell addresses, whatever its source.
RegionMap = list[list[tuple[int, int]]]

# N -> (box_rows, box_cols): the classic box convention this board size tiles
# by. A size absent here has no classic box convention (issue #77) —
# `region_map_for` refuses rather than guessing one.
BOX_SHAPE: dict[int, tuple[int, int]] = {4: (2, 2), 6: (2, 3), 9: (3, 3)}


def classic_boxes(board_size: int = 9, box_size: int = BOX_SIZE) -> RegionMap:
    """The classic 3x3-box partition of a 9x9 board (spec #4, decision 7):
    row/col bands of `box_size` cells, read left-to-right, top-to-bottom.
    """
    bands = board_size // box_size
    return [
        [
            (band_row * box_size + r, band_col * box_size + c)
            for r in range(1, box_size + 1)
            for c in range(1, box_size + 1)
        ]
        for band_row in range(bands)
        for band_col in range(bands)
    ]


def box_regions(size: int, box_rows: int, box_cols: int) -> RegionMap:
    """The box partition of a `size`x`size` board tiled by `box_rows` x
    `box_cols` boxes (issue #77): row/col bands read left-to-right,
    top-to-bottom. `box_regions(9, 3, 3)` reproduces `classic_boxes`
    exactly — the same formula, generalized off one fixed board size.
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


def render_grid(grid: list[list[str]], values: dict[str, int]) -> str:
    """A solved grid as text, box-banded by the board's own shape (issue
    #77): a double space between box columns, a blank line between box rows.
    A size outside `BOX_SHAPE` renders as one ungrouped block — the region
    rule (and so a box shape) isn't required to reach a witness. The box
    banding lives here — the module that owns regions — so a caller (the
    CLI, or any future consumer) prints what `board`/`regions` render rather
    than re-deriving the geometry itself.
    """
    size = len(grid)
    box_rows, box_cols = BOX_SHAPE.get(size, (size, size))
    lines: list[str] = []
    for i, row in enumerate(grid):
        cells = [str(values[name]) for name in row]
        groups = [cells[c : c + box_cols] for c in range(0, len(cells), box_cols)]
        lines.append("  ".join(" ".join(group) for group in groups))
        if (i + 1) % box_rows == 0 and i + 1 < len(grid):
            lines.append("")
    return "\n".join(lines)
