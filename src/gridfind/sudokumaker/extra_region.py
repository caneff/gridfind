"""The `type 305` extra-region decoder: SudokuMaker's windoku-style extra
region, one wire block per drawn window.

Each enabled block's flat `cells` list becomes one `extra-region` `Constraint`
carrying `params = {cells}` — that window's own group of cells — through
`boundary.enabled_block_addresses`, the one home the flat-cells clue decoders
(this and row/col indexing) share for resolving a block's cells and
warn-dropping an empty one. `layers.door` then folds every such constraint
into one `DistinctOverGroups` (via `distinct.extra_regions_from`), each window
a group of the one combined all-different partition — the same rule rows, cols,
and regions ride.
"""

from __future__ import annotations

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_block_addresses
from gridfind.sudokumaker.wire_types import EXTRA_REGION_TYPE


def extra_region_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    return [
        Constraint("extra-region", params={"cells": cells})
        for cells in enabled_block_addresses(
            buckets, EXTRA_REGION_TYPE, size, "extra-region"
        )
    ]
