"""The `type 401` whisper-line decoder: the first wire type of the
nine-relation line-clue family (spec #672), and the pattern every sibling
relation's own decoder follows — `thermo_constraints` (`cages.py`) is the
prior-art template for a `lines`-path block, adapted to this family's shared
`Constraint("line", ...)` shape instead of thermo's own `thermo` type.
"""

from __future__ import annotations

from typing import cast

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.addresses import addresses
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import WHISPER_TYPE


def whisper_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 401` whisper lines as `line` `Constraint`s: each path's raw
    indices map row-major to addresses, order preserved, alongside the
    block's own `minDifference` — carried through verbatim, never defaulted,
    so a block that omits it surfaces the gap at the `Line` layer
    (`params["minDifference"]` bare subscript) rather than here. A `disabled`
    block is skipped entirely; an empty `lines` list adds nothing. The
    cosmetic `style` object is ignored."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, WHISPER_TYPE):
        paths = cast("list[list[int]]", block.get("lines", []))
        if not paths:
            continue
        min_difference = block["minDifference"]
        for path in paths:
            path_addresses = addresses(path, size)
            params: dict[str, object] = {
                "relation": "whisper",
                "path": path_addresses,
                "minDifference": min_difference,
            }
            decoded.append(Constraint("line", params=params))
    return decoded
