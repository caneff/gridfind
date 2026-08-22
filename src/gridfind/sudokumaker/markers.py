"""The display-only marker colorizer (`colorize_marker_cages`) that ranks the
marker kinds a link actually carries onto a fixed palette — name
classification itself lives in `naming.classify` (ADR-0012, ADR-0016,
ADR-0018); this module only reads its result. The S-cell presence/pinning
signals a marker kind feeds are read in `cages.cosmetic_cage_constraints`'s
single walk over the block, not here. The public `MARKER_LABELS` dict is the
role -> accepted-names table, built once from `naming.aliases_by_role` and
read directly by `setter_guide.py`'s cage-name-alias rendering — the public
seam that keeps it off `naming`'s private grouping; `"constant"`'s only
static alias is `Nullifier`, since `Constant <N>` is a parameterized name
naming.py parses rather than a fixed key.
"""

from __future__ import annotations

import json
from typing import Any, cast

from gridfind.sudokumaker.boundary import bucket_constraints_by_type, enabled_blocks
from gridfind.sudokumaker.naming import Role, aliases_by_role, classify
from gridfind.sudokumaker.wire_types import COSMETIC_CAGE_TYPE

# A low-saturation display palette for named marker cages, cosmetic only —
# written onto the `type 2001` block's own `color` field, a field
# `link_to_puzzle` never reads. Index 0 is red: the slot a link's lone marker
# type always takes, and the slot S-cell takes first when a link mixes marker
# types (`_MARKER_KIND_PRIORITY`, near `colorize_marker_cages`).
_MARKER_COLOR_PALETTE: tuple[str, ...] = ("#fd2323ff", "#2372fdff")

# Role -> its accepted `type 2001` names, the public seam `setter_guide.py`
# reads for cage-name-alias rendering. Built from `naming.aliases_by_role` so
# the alias data keeps one home (the name -> shape registry); this exposes it
# publicly without a second copy. `naming.classify` classifies through
# `naming.named_component`, not this table, so the two cannot drift.
MARKER_LABELS: dict[str, frozenset[str]] = aliases_by_role()


# The order `colorize_marker_cages` claims `_MARKER_COLOR_PALETTE` slots in
# when a link carries more than one marker type — S-cell first, so it always
# wins red over Doubler/Constant on a mixed link. A link mixing Doubler and
# Constant marker cages is refused at decode time (ADR-0016), but this
# raw-JSON colorizer runs before any decode validation, so both still rank
# here for a document that pairs one of them with S-cell.
_MARKER_KIND_PRIORITY: tuple[Role, ...] = ("s-cell", "doubler", "constant")


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
    display-only: `link_to_puzzle` never reads a cosmetic-cage block's `style`,
    so a decode of the result agrees with a decode of `document`."""
    colored: dict[str, object] = json.loads(json.dumps(document))
    puzzle_data = cast("dict[str, object]", colored["puzzle"])
    buckets = bucket_constraints_by_type(puzzle_data)
    blocks = list(enabled_blocks(buckets, COSMETIC_CAGE_TYPE))
    present_kinds = {classify(block.get("name")) for block in blocks}
    color_of_kind = dict(
        zip(
            (kind for kind in _MARKER_KIND_PRIORITY if kind in present_kinds),
            _MARKER_COLOR_PALETTE,
            strict=False,
        )
    )
    for block in blocks:
        color = color_of_kind.get(classify(block.get("name")))
        if color is not None:
            style = cast("dict[str, Any]", block.setdefault("style", {}))
            cage_style = cast("dict[str, Any]", style.setdefault("cage", {}))
            cage_style["color"] = color
            text_style = cast("dict[str, Any]", style.setdefault("text", {}))
            text_style["color"] = color
    return colored
