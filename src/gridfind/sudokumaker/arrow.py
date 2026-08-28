"""The `type 408` arrow decoder: a block's top-level `bulbsWithArrows` list,
each entry naming its own `bulbCells` and one or more `arrows` shaft paths
(`wire_types.ARROW_TYPE`) — decoded one `arrow` `Constraint` per entry,
carrying `bulb` and `arrows` cell addresses in wire order for the `Arrow`
layer.

Decode itself never refuses an empty `bulbCells`, an empty `arrows` list, or
a zero-cell shaft — mirroring `equality-cage`'s own odd-cell-count posture
(`layers/equality_cage.py`): the `Arrow` layer raises `MalformedPuzzleError`
once the puzzle reaches emit, where the same check also covers a constraint
built in memory rather than decoded off a link.
"""

from __future__ import annotations

from typing import Any, cast

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.addresses import addresses
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import ARROW_TYPE


def arrow_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """Every enabled `type 408` block's `bulbsWithArrows` decoded to one
    `arrow` `Constraint` per entry: `bulbCells` and each `arrows` path
    resolved to addresses, order preserved."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, ARROW_TYPE):
        bulbs = cast("list[dict[str, Any]]", block.get("bulbsWithArrows", []))
        for entry in bulbs:
            bulb_cells = cast("list[int]", entry.get("bulbCells", []))
            shafts = cast("list[list[int]]", entry.get("arrows", []))
            decoded.append(
                Constraint(
                    "arrow",
                    params={
                        "bulb": addresses(bulb_cells, size),
                        "arrows": [addresses(shaft, size) for shaft in shafts],
                    },
                )
            )
    return decoded
