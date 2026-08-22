"""The `type 100`/`101` even/odd decoder: one shared handler, parameterized
by parity, builds both — the sibling-type shape `_indexing_handler` uses for
`type 600`/`601`, extended here to even/odd's own flat-cells block.

Each enabled block's flat `cells` list becomes one `parity` `Constraint` per
block, carrying `params = {parity, cells}` — the per-clue parity the
`Parity` layer reads back, never re-derived from the wire type once decoded.
Cells are resolved and an empty block warn-dropped through
`boundary.enabled_block_addresses`, the one home this and the extra-region/
indexing decoders share for that flat-cells-block step.
"""

from __future__ import annotations

from collections.abc import Callable

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_block_addresses
from gridfind.sudokumaker.wire_types import EVEN_TYPE, ODD_TYPE


def _parity_handler(
    wire_type: int, parity: str, name: str
) -> Callable[[ConstraintBuckets, int], list[Constraint]]:
    def handler(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
        return [
            Constraint("parity", params={"parity": parity, "cells": cells})
            for cells in enabled_block_addresses(buckets, wire_type, size, name)
        ]

    return handler


even_constraints = _parity_handler(EVEN_TYPE, "even", "even")
odd_constraints = _parity_handler(ODD_TYPE, "odd", "odd")
