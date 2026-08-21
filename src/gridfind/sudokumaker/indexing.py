"""The `type 600`/`601` indexing-clue decoder (the 159 self-reference): one
shared handler, parameterized by axis, builds both — the sibling-type shape
`_global_toggle_handler` uses for the bare toggles, extended here to a block
that carries a payload.

Each enabled block's flat `cells` list becomes one `indexing` `Constraint` per
block, carrying `params = {axis, cells}` — the per-clue axis the `Indexing`
layer reads back, never re-derived from the wire type once decoded. Cells are
resolved and an empty block warn-dropped through
`boundary.enabled_block_addresses`, the one home this and the extra-region
decoder share for that flat-cells-block step.
"""

from __future__ import annotations

from collections.abc import Callable

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_block_addresses
from gridfind.sudokumaker.wire_types import INDEXING_COL_TYPE, INDEXING_ROW_TYPE


def _indexing_handler(
    wire_type: int, axis: str, name: str
) -> Callable[[ConstraintBuckets, int], list[Constraint]]:
    def handler(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
        return [
            Constraint("indexing", params={"axis": axis, "cells": cells})
            for cells in enabled_block_addresses(buckets, wire_type, size, name)
        ]

    return handler


row_indexing_constraints = _indexing_handler(INDEXING_ROW_TYPE, "row", "row-indexing")
col_indexing_constraints = _indexing_handler(INDEXING_COL_TYPE, "col", "col-indexing")
