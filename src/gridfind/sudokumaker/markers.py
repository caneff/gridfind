"""Named marker-cage classification (ADR-0012, homed here in #443, routed
through the name -> shape registry in #434): a `type 2001` cosmetic-cage
block's top-level `name` sorted into `"ordinary"`, `"doubler"`, `"s-cell"`, or
`"unrecognized"` (`cosmetic_cage_kind`), the two S-cell channels that read it —
enablement by block *presence* (`_has_scell_marker_block`) and pinning by cell
*membership* (`_scell_marker_values`) — and the display-only marker colorizer
(`colorize_marker_cages`) that ranks the marker kinds a link actually carries
onto a fixed palette.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from gridfind.sudokumaker.boundary import (
    ConstraintBuckets,
    _bucket_constraints_by_type,
    _enabled_blocks,
)
from gridfind.sudokumaker.cells import _addresses
from gridfind.sudokumaker.naming import _named_component

# type 2001 is a cosmetic-cage block: `{cages: [{value: str, cells: [...]}]}`,
# the same nested wire shape as a `type 301` killer block — SudokuMaker's
# decoration tool, not the killer-cage tool (ADR-0008). A numeric string
# `value` graduates a cage to a real killer sum, the only channel an
# out-of-range cage sum (a doubler inside a cage) reaches gridfind through,
# since the killer-cage tool refuses to store one.
_COSMETIC_CAGE_TYPE = 2001

# A low-saturation display palette for named marker cages, cosmetic only —
# written onto the `type 2001` block's own `color` field, a field
# `decode_link` never reads. Index 0 is red: the slot a link's lone marker
# type always takes, and the slot S-cell takes first when a link mixes marker
# types (`_MARKER_KIND_PRIORITY`, near `colorize_marker_cages`).
_MARKER_COLOR_PALETTE: tuple[str, ...] = ("#fd2323ff", "#2372fdff")

CosmeticCageKind = Literal["ordinary", "doubler", "s-cell", "unrecognized"]


def cosmetic_cage_kind(name: object) -> CosmeticCageKind:
    """Classify a `type 2001` block's top-level `name` (ADR-0012) into one of
    four kinds: `"ordinary"` (absent/blank, or a decorative `Sum`/`Killer`
    label on a genuine cage — the registry's `"killer"` role), `"doubler"` (a
    `Doubler` position marker), `"s-cell"` (an `S-cell`/`Schrödinger` position
    marker), or `"unrecognized"` (a name `decode_link` cannot answer for).
    Matching is case-insensitive and trimmed, via the shared
    `naming._named_component` lookup.

    This is the one home the named-cosmetic-cage reads route through — the cage
    decoder, the S-cell presence and membership channels, marker colorizing,
    and dev tools that recognize a marker block without decoding the whole
    link all switch on this kind."""
    component = _named_component(name)
    if component is None:
        return "unrecognized" if isinstance(name, str) and name.strip() else "ordinary"
    return "ordinary" if component.role == "killer" else component.role


def _is_scell_block(block: dict[Any, Any]) -> bool:
    """True when a `type 2001` block is named `S-cell`/`Schrödinger`
    (`cosmetic_cage_kind`, backed by the `naming` registry). The one predicate
    both S-cell channels share, so presence and pinning agree on the label set
    by construction: `_has_scell_marker_block` reads it for enablement by
    presence, `_scell_marker_values` for pinning by membership (ADR-0014)."""
    return cosmetic_cage_kind(block.get("name")) == "s-cell"


def _scell_marker_values(buckets: ConstraintBuckets, size: int) -> dict[str, object]:
    """Every cell address declared an S-cell by a `type 2001` cosmetic-cage
    block named `S-cell`/`Schrödinger`, mapped to its
    marker cage's own raw `value` (ADR-0014) — the pair/half/bare source
    `_decode_cell` reads for that address. A multi-cell cage's `value` applies
    uniformly to every cell it contains (CONTEXT.md `marker cage`). The
    mapping's key set doubles as the address set that routes a cell through the
    S-cell branch — the *membership* channel that pins known S-cells. It does
    not enable the mode: `_has_scell_marker_block` reads block *presence* for
    that, so an empty block enables Schrödinger with this mapping empty
    (ADR-0014). A `disabled` block contributes nothing, exactly as its cage
    rule would not."""
    return {
        address: cage.get("value")
        for block in _enabled_blocks(buckets, _COSMETIC_CAGE_TYPE)
        if _is_scell_block(block)
        for cage in cast("list[dict[str, Any]]", block.get("cages", []))
        for address in _addresses(cage["cells"], size)
    }


def _has_scell_marker_block(buckets: ConstraintBuckets) -> bool:
    """True when an enabled `type 2001` cosmetic-cage block is named
    `S-cell`/`Schrödinger`, regardless of whether it
    names any cells. This block *presence* enables Schrödinger mode (ADR-0014):
    the domain widens to `0…N` and a `schrodinger` constraint stands up, giving
    every cell the `is_s` freedom the solver discovers S-cells with. An empty
    block means "discover them all"; a block that names cells additionally
    pins those as known S-cells (`_scell_marker_values`)."""
    blocks = _enabled_blocks(buckets, _COSMETIC_CAGE_TYPE)
    return any(_is_scell_block(block) for block in blocks)


# The order `colorize_marker_cages` claims `_MARKER_COLOR_PALETTE` slots in
# when a link carries more than one marker type — S-cell first, so it always
# wins red over Doubler on a mixed link.
_MARKER_KIND_PRIORITY: tuple[CosmeticCageKind, ...] = ("s-cell", "doubler")


def colorize_marker_cages(document: dict[str, object]) -> dict[str, object]:
    """`document` with every named marker cage's `type 2001` block stamped
    with a display color at `style.cage.color` — the field SudokuMaker renders a
    cosmetic cage's fill from — on a copy; `document` itself is untouched. The
    color a marker type gets depends on which marker types the
    *link* actually carries, not a fixed per-type constant: the marker types
    present among `document`'s enabled `type 2001` blocks are ranked by
    `_MARKER_KIND_PRIORITY` and assigned `_MARKER_COLOR_PALETTE` slots in that
    order, so a link with only one marker type always colors it red
    (`_MARKER_COLOR_PALETTE[0]`), whichever type it is, while a link mixing
    types gives S-cell red and Doubler the next slot. An ordinary (unnamed or
    Sum/Killer-labelled) cosmetic-cage block, an unrecognized name, and every
    other constraint type ride through uncolored. The written field is
    display-only: `decode_link` never reads a cosmetic-cage block's `style`,
    so a decode of the result agrees with a decode of `document`."""
    colored: dict[str, object] = json.loads(json.dumps(document))
    puzzle_data = cast("dict[str, object]", colored["puzzle"])
    buckets = _bucket_constraints_by_type(puzzle_data)
    blocks = list(_enabled_blocks(buckets, _COSMETIC_CAGE_TYPE))
    present_kinds = {cosmetic_cage_kind(block.get("name")) for block in blocks}
    color_of_kind = dict(
        zip(
            (kind for kind in _MARKER_KIND_PRIORITY if kind in present_kinds),
            _MARKER_COLOR_PALETTE,
            strict=False,
        )
    )
    for block in blocks:
        color = color_of_kind.get(cosmetic_cage_kind(block.get("name")))
        if color is not None:
            style = cast("dict[str, Any]", block.setdefault("style", {}))
            cage_style = cast("dict[str, Any]", style.setdefault("cage", {}))
            cage_style["color"] = color
            text_style = cast("dict[str, Any]", style.setdefault("text", {}))
            text_style["color"] = color
    return colored
