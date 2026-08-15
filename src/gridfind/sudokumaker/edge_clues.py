"""The three edge-clue types — XV (`type 202`), white-kropki (`type 200`),
black-kropki (`type 201`) — which share one wire shape (`clues: [{value,
edge}], negative: [...]`) and one decode walk (`_edge_clue_constraints`) built
on the shared edge-to-cell-pair primitive `_edge_to_pair`.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any, cast

from gridfind.cell_geometry import cell_address
from gridfind.layers import ALIAS_REGISTRY
from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, _as_int, _enabled_blocks

# type 202 is XV: `clues: [{value, edge}], negative:
# [...]`. `value` selects the existing group-sum alias — 10 is X, 5 is V
# — never a raw `sum`, so a puzzle carrying both an XV clue and
# a literal group-sum on the same cells still hits the alias's own
# fixed-param conflict check in `expand_constraints`. Read off
# `gridfind.layers.ALIAS_REGISTRY` rather than restated here — the
# sum each alias fixes is stated once, in the registry that also builds it.
_XV_TYPE = 202
_XV_ALIASES: dict[int, str] = {
    cast("int", fixed["sum"]): alias
    for alias, (canonical, fixed) in ALIAS_REGISTRY.items()
    if canonical == "group-sum" and "sum" in fixed
}

# type 200 is white-kropki: `clues: [{value, edge}],
# negative: [...]`, the same wire shape as XV. The type number *is* the
# white/black discriminator — 200 is white/difference, 201 black/ratio — so
# `value` is the target difference, honored verbatim onto the existing
# `pair-difference` layer (a labelled non-1 value is never coerced to 1).
_KROPKI_WHITE_TYPE = 200

# type 201 is black-kropki: the same `clues:
# [{value, edge}], negative: [...]` wire shape as white kropki, `value` read
# as the target integer ratio `k` onto the `pair-ratio` layer (a labelled
# non-2 dot is never coerced to 2). A non-integer `value` raises at decode —
# modeling a wrong verdict would be worse than refusing the link.
_KROPKI_BLACK_TYPE = 201


def _warn_dropped_negative(block: dict[str, Any], label: str) -> None:
    """Warn to stderr when a kropki/XV `block` carries a non-empty `negative`
    list: gridfind models only the positive clues, so the verdict
    is computed without the negative rule and the drop must never be silent."""
    negative = block.get("negative")
    if isinstance(negative, list) and negative:
        print(
            f"warning: ignoring {label} negative constraint "
            "— verdict computed without it",
            file=sys.stderr,
        )


def _edge_to_pair(edge: int, size: int) -> tuple[str, str]:
    """An XV/kropki `edge` integer decoded to its two orthogonally-adjacent
    cell addresses, the primitive shared by the XV and
    white-kropki decoders.

    Edges are enumerated in row-major blocks of `2 * size`, one block per
    0-indexed row `r0`: within a block, offset `1..size-1` is a horizontal
    (left/right) pair starting `r0`, and offset `size..2*size-1` is a
    vertical (up/down) pair starting `r0` — the two closed-form formulas
    (`edge = 2N*r0 + c0 + 1` horizontal, `edge = 2N*r0 + c0 + N` vertical)
    inverted by `divmod`. Oracle-verified against a real link: X @ 70
    = R4C8/R5C8, V @ 103 = R6C5/R7C5 (vertical), kropki @ 75 = R5C3/R5C4, @
    132 = R8C6/R8C7 (horizontal), all on a 9x9 board.

    Raises `ValueError` when `edge` names no in-bounds pair on a `size`x`size`
    board (an out-of-range offset, or a row with no room for the pair)."""
    block = 2 * size
    r0, offset = divmod(edge, block)
    if 1 <= offset <= size - 1 and 0 <= r0 <= size - 1:
        c0 = offset - 1
        return cell_address(r0 + 1, c0 + 1), cell_address(r0 + 1, c0 + 2)
    if size <= offset <= block - 1 and 0 <= r0 <= size - 2:
        c0 = offset - size
        return cell_address(r0 + 1, c0 + 1), cell_address(r0 + 2, c0 + 1)
    msg = (
        f"non-classic link: edge {edge!r} does not name a valid cell pair "
        f"on a {size}x{size} board"
    )
    raise ValueError(msg)


def _edge_clue_constraints(
    buckets: ConstraintBuckets,
    size: int,
    type_: int,
    build_clue: Callable[[object, str, str], Constraint],
    label: str,
) -> list[Constraint]:
    """The shared decode walk behind the edge-clue types — XV, white-kropki,
    black-kropki — which share one wire shape (`clues: [{value, edge}],
    negative: [...]`). Every enabled `type_` block: each clue's `edge` decodes
    to its orthogonally-adjacent pair via `_edge_to_pair`, then
    `build_clue(value, a, b)` turns the clue's raw `value` and that pair into
    one `Constraint`. A `disabled` block is skipped entirely; a non-empty
    `negative` list is warn-and-dropped to stderr under `label` — the caller's
    `DECODER_REGISTRY` display name — while its positive clues still decode.
    `build_clue` carries the single per-type variation — an alias lookup, a
    `diff`, a ratio `k`."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(buckets, type_):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        for clue in clues:
            a, b = _edge_to_pair(clue["edge"], size)
            decoded.append(build_clue(clue["value"], a, b))
        _warn_dropped_negative(block, label)
    return decoded


def _xv_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 202` XV clues as aliased group-sum `Constraint`s: `value`
    selects the existing `x`/`v` alias (10/5), or the link is refused — no
    other value names an XV sum. See `_edge_clue_constraints` for the walk."""

    def build(value: object, a: str, b: str) -> Constraint:
        # The XV wire value is a JSON number; the cast satisfies the int-keyed
        # lookup, and a non-int value simply misses it and raises below.
        alias = _XV_ALIASES.get(cast("int", value))
        if alias is None:
            msg = (
                f"non-classic link: XV clue value {value!r} is neither X (10) nor V (5)"
            )
            raise ValueError(msg)
        return Constraint(alias, params={"cells": [a, b]})

    return _edge_clue_constraints(buckets, size, _XV_TYPE, build, "XV")


def _kropki_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 200` white-kropki clues as `pair-difference` `Constraint`s:
    `value` is the target difference passed verbatim as `diff` — a labelled
    non-1 dot is honored at that value, never coerced to the consecutive
    default. `type 201` (black/ratio) has its own handler. See
    `_edge_clue_constraints` for the walk."""

    def build(value: object, a: str, b: str) -> Constraint:
        return Constraint("pair-difference", params={"cells": [a, b], "diff": value})

    return _edge_clue_constraints(
        buckets, size, _KROPKI_WHITE_TYPE, build, "white-kropki"
    )


def _black_kropki_constraints(
    buckets: ConstraintBuckets, size: int
) -> list[Constraint]:
    """The `type 201` black-kropki clues as `pair-ratio` `Constraint`s: `value`
    is the target integer ratio `k`, honored verbatim — a labelled non-2 dot
    is never coerced to 2. `value` must be an int (`_as_int`); a non-integer
    ratio raises `ValueError` at decode rather than modeling a wrong verdict.
    See `_edge_clue_constraints` for the walk."""

    def build(value: object, a: str, b: str) -> Constraint:
        k = _as_int(value, "black-kropki value")
        return Constraint("pair-ratio", params={"cells": [a, b], "k": k})

    return _edge_clue_constraints(
        buckets, size, _KROPKI_BLACK_TYPE, build, "black-kropki"
    )
