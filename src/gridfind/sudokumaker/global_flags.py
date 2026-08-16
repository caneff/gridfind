"""Global-flag component recognition — the third named-component shape
(`naming._Shape`, spec #431/#436), alongside `cage-selector`/`cell-marker`: a
name needing no payload at all, recognized through the shared
`naming.named_component` lookup on either name-bearing carrier — a `type
1000` custom constraint's `definition.name`, or a `type 2001` cosmetic
cage's top-level `name`. `Somedoku` is the first (and so far only) name
registered against this shape: its presence alone, on either carrier, turns
on the puzzle-wide `line-count-distinct` rule, cells and value ignored on
both.
"""

from __future__ import annotations

from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.naming import named_component
from gridfind.sudokumaker.registry import constraint_name
from gridfind.sudokumaker.wire_types import COSMETIC_CAGE_TYPE, CUSTOM_CONSTRAINT_TYPE


def has_somedoku_component(buckets: ConstraintBuckets) -> bool:
    """True when an enabled block on either name-bearing carrier names the
    `Somedoku` global-flag component (`naming.named_component`'s
    `"somedoku"` role) — a `type 1000` custom constraint's `definition.name`
    read via `registry.constraint_name`, or a `type 2001` cosmetic cage's
    top-level `name`. Cells and value are ignored on both carriers; presence
    of the name is the whole signal, exactly as a global toggle's bare
    enabled presence is its whole rule (`registry._global_toggle_handler`).
    A `disabled` block never counts (`enabled_blocks`)."""
    for block in enabled_blocks(buckets, CUSTOM_CONSTRAINT_TYPE):
        component = named_component(constraint_name(block))
        if component is not None and component.role == "somedoku":
            return True
    for block in enabled_blocks(buckets, COSMETIC_CAGE_TYPE):
        component = named_component(block.get("name"))
        if component is not None and component.role == "somedoku":
            return True
    return False
