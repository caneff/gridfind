"""The flat-cells clue decoders: `type 100`/`101` (even/odd parity), `type
305` (extra-region), and `type 600`/`601` (row/col indexing) each read one
enabled block's flat `cells` list into a single `Constraint` of that clue's
type — differing only in the constraint-type string and an optional extra
param (parity's `parity` value, indexing's `axis`; extra-region carries
neither). One shared handler factory, parameterized by wire type,
constraint type, drop-warning name, and that optional extra param, builds
all five as `DECODER_REGISTRY` rows over `boundary.enabled_block_addresses`
— the one home that resolves a block's cells and warn-drops an empty one.
"""

from __future__ import annotations

from collections.abc import Callable

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_block_addresses
from gridfind.sudokumaker.wire_types import (
    EVEN_TYPE,
    EXTRA_REGION_TYPE,
    INDEXING_COL_TYPE,
    INDEXING_ROW_TYPE,
    ODD_TYPE,
)


def _flat_cells_handler(
    wire_type: int,
    constraint_type: str,
    name: str,
    extra_params: dict[str, str] | None = None,
) -> Callable[[ConstraintBuckets, int], list[Constraint]]:
    def handler(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
        return [
            Constraint(constraint_type, params={**(extra_params or {}), "cells": cells})
            for cells in enabled_block_addresses(buckets, wire_type, size, name)
        ]

    return handler


extra_region_constraints = _flat_cells_handler(
    EXTRA_REGION_TYPE, "extra-region", "extra-region"
)
row_indexing_constraints = _flat_cells_handler(
    INDEXING_ROW_TYPE, "indexing", "row-indexing", {"axis": "row"}
)
col_indexing_constraints = _flat_cells_handler(
    INDEXING_COL_TYPE, "indexing", "col-indexing", {"axis": "col"}
)
even_constraints = _flat_cells_handler(EVEN_TYPE, "parity", "even", {"parity": "even"})
odd_constraints = _flat_cells_handler(ODD_TYPE, "parity", "odd", {"parity": "odd"})
