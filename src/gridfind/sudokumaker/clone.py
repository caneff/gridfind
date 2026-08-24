"""The `type 302` clone decoder: each group under a block's `input.groups`
becomes one `clone` `Constraint` naming that group's cells, which the `Clone`
layer holds to an equal digit set (ADR-0019 dec 4).

The wire shape is `{input: {groups: [{cells: [...]}]}}` — the nested
`input.groups` form `dropped.has_live_data` already reads to tell a populated
clone block from an inert one, so this decoder and that active/inert predicate
share one reading of the shape. A group with fewer than two cells names no pair
to equate, so it contributes no constraint and no warning — the inert extra a
real link routinely carries (`dropped_test`'s empty group).
"""

from __future__ import annotations

from typing import Any, cast

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.addresses import addresses
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import CLONE_TYPE


def clone_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """Every enabled `type 302` block's `input.groups` decoded to one `clone`
    `Constraint` per group holding two or more cells: each group's raw cell
    indices resolved to addresses, carried through for the `Clone` layer's
    digit-set-equality check. A group with fewer than two cells is dropped
    quietly — it names no pair to hold equal."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, CLONE_TYPE):
        payload = block.get("input")
        if not isinstance(payload, dict):
            continue
        groups = cast("list[dict[str, Any]]", payload.get("groups", []))
        for group in groups:
            cells = cast("list[int]", group.get("cells", []))
            if len(cells) < 2:
                continue
            decoded.append(
                Constraint("clone", params={"cells": addresses(cells, size)})
            )
    return decoded
