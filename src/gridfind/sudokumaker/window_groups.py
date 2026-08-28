"""The `type 16` window-groups decoder: global entropy and global mod are
one wire shape, `{type:16, groups:[bitmask, …]}` — SudokuMaker distinguishes
them only by which digit-bitmask groups populate `groups`
(`wire_types.GLOBAL_ENTROPY_TYPE`). Each enabled block decodes to its own
`window-groups` `Constraint`, `groups` carried through verbatim; a link
enabling two blocks (entropy plus mod together) yields two constraints, both
enforced (`layers/window_groups.py`).
"""

from __future__ import annotations

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import GLOBAL_ENTROPY_TYPE


def window_groups_constraints(
    buckets: ConstraintBuckets, size: int
) -> list[Constraint]:
    """Every enabled `type 16` block as its own `window-groups` `Constraint`,
    carrying the block's own `groups` verbatim — a bare subscript, never
    defaulted, so a block missing `groups` surfaces the gap as `KeyError`
    rather than silently deciding an empty rule."""
    return [
        Constraint("window-groups", params={"groups": block["groups"]})
        for block in enabled_blocks(buckets, GLOBAL_ENTROPY_TYPE)
    ]
