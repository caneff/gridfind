"""Named marker-cage classification (ADR-0012, homed here in #443, routed
through the name -> shape registry in #434, extended with a parameterized
`"constant"` kind by ADR-0016, a payload-less `"somedoku"` kind, and two more
cage-selector kinds, `"equality"` and `"rellik"` (ADR-0018)): a
`type 2001` cosmetic-cage block's top-level
`name` sorted into `"unnamed"`, `"killer"`, `"equality"`, `"rellik"`,
`"doubler"`, `"s-cell"`, `"constant"`, `"somedoku"`, or `"unrecognized"`
(`cosmetic_cage_kind`), and
the display-only marker colorizer (`colorize_marker_cages`) that ranks the
marker kinds a link actually carries onto a fixed palette. The S-cell
presence/pinning signals `cosmetic_cage_kind` feeds are read in
`cages.cosmetic_cage_constraints`'s single walk over the block, not here. The
public `MARKER_LABELS` dict is the role -> accepted-names table, built once
from `naming.aliases_by_role` and read directly by `setter_guide.py`'s
cage-name-alias rendering — the public seam that keeps it off `naming`'s
private grouping; `"constant"`'s only static alias is `Nullifier`, since
`Constant <N>` is a parameterized name naming.py parses rather than a fixed
key.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from gridfind.sudokumaker.boundary import bucket_constraints_by_type, enabled_blocks
from gridfind.sudokumaker.naming import aliases_by_role, named_component
from gridfind.sudokumaker.wire_types import COSMETIC_CAGE_TYPE

# A low-saturation display palette for named marker cages, cosmetic only —
# written onto the `type 2001` block's own `color` field, a field
# `decode_link` never reads. Index 0 is red: the slot a link's lone marker
# type always takes, and the slot S-cell takes first when a link mixes marker
# types (`_MARKER_KIND_PRIORITY`, near `colorize_marker_cages`).
_MARKER_COLOR_PALETTE: tuple[str, ...] = ("#fd2323ff", "#2372fdff")

CosmeticCageKind = Literal[
    "unnamed",
    "killer",
    "equality",
    "rellik",
    "doubler",
    "s-cell",
    "constant",
    "somedoku",
    "unrecognized",
]

# Role -> its accepted `type 2001` names, the public seam `setter_guide.py`
# reads for cage-name-alias rendering. Built from `naming.aliases_by_role` so
# the alias data keeps one home (the name -> shape registry); this exposes it
# publicly without a second copy. `cosmetic_cage_kind` classifies through
# `naming.named_component`, not this table, so the two cannot drift.
MARKER_LABELS: dict[str, frozenset[str]] = aliases_by_role()


def cosmetic_cage_kind(name: object) -> CosmeticCageKind:
    """Classify a `type 2001` block's top-level `name` (ADR-0012, extended by
    ADR-0016 and ADR-0018) into one of nine kinds: `"unnamed"`
    (absent/blank — a purely decorative block that carries no rule),
    `"killer"` (a recognized `Sum`/`Killer` label that selects the
    killer-cage rule), `"equality"` (a recognized `Equality` label that
    selects `cage` + `equality-cage`), `"rellik"` (a recognized `Rellik`/`Anti`
    label that selects the anti-cage subset-sum ban, the cage's numeric value
    read as the forbidden total), `"doubler"` (a `Doubler` position marker),
    `"s-cell"` (an `S-cell`/`Schrödinger` position marker), `"constant"` (a
    `Constant <N>`/`Nullifier` position marker whose `k` is read from the name
    itself), `"somedoku"` (the payload-less `Somedoku` global flag — cells and
    value ignored), or `"unrecognized"` (a name `decode_link` cannot answer
    for — a bare `Constant` with no parseable integer lands here too, never
    silently `k = 0`). `"unnamed"` and `"unrecognized"` share the same fate
    downstream — a loud stderr warn-drop, never a rule (ADR-0012) — but stay
    distinct kinds here since the warning they produce names the block
    differently. Matching is case-insensitive and trimmed, via the shared
    `naming.named_component` lookup.

    This is the one home the named-cosmetic-cage reads route through — the cage
    decoder, the S-cell presence and membership channels, marker colorizing,
    and dev tools that recognize a marker block without decoding the whole
    link all switch on this kind."""
    component = named_component(name)
    if component is None:
        return "unrecognized" if isinstance(name, str) and name.strip() else "unnamed"
    return component.role


# The order `colorize_marker_cages` claims `_MARKER_COLOR_PALETTE` slots in
# when a link carries more than one marker type — S-cell first, so it always
# wins red over Doubler/Constant on a mixed link. A link mixing Doubler and
# Constant marker cages is refused at decode time (ADR-0016), but this
# raw-JSON colorizer runs before any decode validation, so both still rank
# here for a document that pairs one of them with S-cell.
_MARKER_KIND_PRIORITY: tuple[CosmeticCageKind, ...] = ("s-cell", "doubler", "constant")


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
    types gives S-cell red and Doubler the next slot. An unnamed cosmetic-cage
    block, a Sum/Killer-labelled one, an unrecognized name, and every other
    constraint type ride through uncolored. The written field is
    display-only: `decode_link` never reads a cosmetic-cage block's `style`,
    so a decode of the result agrees with a decode of `document`."""
    colored: dict[str, object] = json.loads(json.dumps(document))
    puzzle_data = cast("dict[str, object]", colored["puzzle"])
    buckets = bucket_constraints_by_type(puzzle_data)
    blocks = list(enabled_blocks(buckets, COSMETIC_CAGE_TYPE))
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
