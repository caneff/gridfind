"""The line-clue family's decoders: one function per wire type, all sharing
the same `lines`-path walk (`_line_constraints`) since every relation decodes
to the identical `Constraint("line", ...)` shape (spec #672) and differs only
in its `relation` alias and whatever block-level knobs that alias reads
(whisper's `minDifference`; renban states none). `thermo_constraints`
(`cages.py`) is the prior-art template for a `lines`-path block this shared
walk itself follows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from gridfind.puzzle import Constraint, JsonValue
from gridfind.sudokumaker.addresses import addresses
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.wire_types import RENBAN_TYPE, WHISPER_TYPE


def _line_constraints(
    buckets: ConstraintBuckets,
    size: int,
    wire_type: int,
    relation: str,
    *,
    block_params: Callable[[dict[str, object]], Mapping[str, JsonValue]] | None = None,
) -> list[Constraint]:
    """Every enabled `wire_type` block's `lines` paths, each its own `line`
    `Constraint` naming `relation`: raw indices map row-major to addresses,
    order preserved, alongside whatever `block_params(block)` reads off the
    block itself (whisper's `minDifference`, read once per block before its
    paths, never defaulted — a block missing it surfaces the gap through the
    bare-subscript reader `block_params` closes over). `None` (renban's case)
    adds no extra params. A `disabled` block is skipped entirely (`
    enabled_blocks`); an empty `lines` list adds nothing. The cosmetic
    `style` object is ignored."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, wire_type):
        paths = cast("list[list[int]]", block.get("lines", []))
        if not paths:
            continue
        extra = block_params(block) if block_params is not None else {}
        for path in paths:
            path_addresses = addresses(path, size)
            params: dict[str, object] = {
                "relation": relation,
                "path": path_addresses,
                **extra,
            }
            decoded.append(Constraint("line", params=params))
    return decoded


def renban_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 400` renban lines as `line` `Constraint`s — no block-level
    knob, renban's own distinctness-and-span rule needs nothing beyond the
    path."""
    return _line_constraints(buckets, size, RENBAN_TYPE, "renban")


def whisper_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 401` whisper lines as `line` `Constraint`s, each carrying the
    block's own `minDifference` verbatim, never defaulted, so a block that
    omits it surfaces the gap at the `Line` layer (`params["minDifference"]`
    bare subscript) rather than here."""
    return _line_constraints(
        buckets,
        size,
        WHISPER_TYPE,
        "whisper",
        block_params=lambda block: {"minDifference": block["minDifference"]},
    )
