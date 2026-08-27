"""The `type 303` quadruple decoder: each enabled block's `clues` list
(`{corner, digits}`) becomes one `quadruple` `Constraint` per clue, its
`corner` resolved to the four cells of a 2x2 block through `corner_to_quad`
— the same `clues`-list wire shape the edge-clue types
(`edge_clues._edge_clue_constraints`) walk, naming a 2x2 block instead of an
orthogonal pair.
"""

from __future__ import annotations

from typing import Any, cast

from gridfind.cell_geometry import format_address
from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import QUADRUPLE_TYPE


def corner_to_quad(corner: int, size: int) -> list[str]:
    """A quadruple clue's `corner` integer decoded to its 2x2 block's four
    cell addresses, top-left/top-right/bottom-left/bottom-right.

    Corners are enumerated row-major over the board's full `(size+1) x
    (size+1)` point lattice — every grid intersection including the border
    — `corner = (size+1)*r0 + c0` for 0-indexed `r0`, `c0` each in
    `0..size`, with `(r0, c0)` itself naming the block's 1-based top-left
    cell. A 4x4 board's `corner: 7` decodes to `R1C2/R1C3/R2C2/R2C3`
    (`divmod(7, 5) == (1, 2)`).

    Only a point strictly inside the border (`1 <= r0 <= size-1` and
    `1 <= c0 <= size-1`) has cells on all four sides; a border point
    (`r0`/`c0` equal to `0` or `size`) is a valid lattice coordinate but
    names no 2x2 block.

    Raises `ValueError` when `corner` does not name an in-bounds 2x2 block
    on a `size`x`size` board (including a board too small to hold one)."""
    span = size + 1
    in_range = 0 <= corner < span * span
    r0, c0 = divmod(corner, span)
    if not in_range or not (1 <= r0 <= size - 1 and 1 <= c0 <= size - 1):
        msg = (
            f"non-classic link: corner {corner!r} does not name a valid "
            f"2x2 block on a {size}x{size} board"
        )
        raise ValueError(msg)
    return [
        format_address(r0, c0),
        format_address(r0, c0 + 1),
        format_address(r0 + 1, c0),
        format_address(r0 + 1, c0 + 1),
    ]


def quad_to_corner(row: int, col: int, size: int) -> int:
    """The `corner` index naming the 2x2 block whose top-left cell is
    1-based `(row, col)` — `corner_to_quad`'s inverse, for a corpus
    synthesizer that knows the block and wants the wire's corner number."""
    return (size + 1) * row + col


def quadruple_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """Every enabled `type 303` block's `clues` list decoded to one
    `quadruple` `Constraint` per clue: `corner` resolved to its four cells
    via `corner_to_quad`, `digits` carried through verbatim for the
    `Quadruple` layer's presence check."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, QUADRUPLE_TYPE):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        for clue in clues:
            cells = corner_to_quad(cast("int", clue["corner"]), size)
            digits = cast("list[int]", clue["digits"])
            decoded.append(
                Constraint("quadruple", params={"cells": cells, "digits": digits})
            )
    return decoded
