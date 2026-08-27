"""The `type 302` clone decoder: a block's top-level `groups` — a list of
raw cell-index lists, no `input` wrapper and no nested `{cells: [...]}`
object — decoded one `clone` `Constraint` per group. Issue #732's real
captured link (`links/found-clone-4x4-human.txt`, wire payload
`{groups: [[0, 14], [1, 15]]}`) disproves the build-time `input.groups`
guess and confirms the flat shape spec #608/#614 originally called for:
"within each group the cells hold equal digit sets" — each group stands
alone, with no relationship to any other group in the same block (the
`Clone` layer holds the group's own cells to an equal digit set, ADR-0019
dec 4).

A group with fewer than two cells names no pair to equate, so it
contributes no constraint and no warning — the inert extra a real link
routinely carries (`dropped_test`'s empty group).
"""

from __future__ import annotations

from typing import cast

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.addresses import addresses
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import CLONE_TYPE


def clone_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """Every enabled `type 302` block's `groups` decoded to one `clone`
    `Constraint` per group holding two or more cells: each group's raw cell
    indices resolved to addresses, carried through for the `Clone` layer's
    digit-set-equality check. A group with fewer than two cells is dropped
    quietly — it names no pair to equate."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, CLONE_TYPE):
        groups = cast("list[list[int]]", block.get("groups", []))
        for cells in groups:
            if len(cells) < 2:
                continue
            decoded.append(
                Constraint("clone", params={"cells": addresses(cells, size)})
            )
    return decoded
