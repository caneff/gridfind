"""The `type 600`/`601` indexing-clue decoder (the 159 self-reference): one
shared handler, parameterized by axis, builds both — the sibling-type shape
`_global_toggle_handler` uses for the bare toggles, extended here to a block
that carries a payload.

Each enabled block's flat `cells` list (row-major raw indices, the same
scheme `cages.addresses` resolves for a thermometer's path) becomes one
`indexing` `Constraint` per block, carrying `params = {axis, cells}` — the
per-clue axis the `Indexing` layer reads back, never re-derived from the
wire type once decoded. A `disabled` block is skipped entirely; the cosmetic
`style` object is ignored. A block with no usable `cells` carries no rule —
gridfind warns to stderr and drops it rather than emitting an empty clue, so
a setter placing a live indexing block SudokuMaker somehow saved with no
marked cells sees why the verdict doesn't reflect it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import cast

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.addresses import addresses
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import INDEXING_COL_TYPE, INDEXING_ROW_TYPE


def _indexing_handler(
    wire_type: int, axis: str, name: str
) -> Callable[[ConstraintBuckets, int], list[Constraint]]:
    def handler(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
        decoded: list[Constraint] = []
        for block in enabled_blocks(buckets, wire_type):
            cells = cast("list[int]", block.get("cells", []))
            if not cells:
                print(
                    f"warning: ignoring {name} block with no cells "
                    "— verdict computed without it",
                    file=sys.stderr,
                )
                continue
            decoded.append(
                Constraint(
                    "indexing", params={"axis": axis, "cells": addresses(cells, size)}
                )
            )
        return decoded

    return handler


row_indexing_constraints = _indexing_handler(INDEXING_ROW_TYPE, "row", "row-indexing")
col_indexing_constraints = _indexing_handler(INDEXING_COL_TYPE, "col", "col-indexing")
