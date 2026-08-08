"""Composition point for the layers package (issue #17).

Assembles the layer registry from the per-layer modules as an explicit list —
no decorator, no import-side-effect auto-discovery — and holds the record
dispatch API (`resolve_records`, `canonical_identity`, `UnknownLayerError`)
that `verdict.py` consumes.

`gridfind.layers` is **internal-only** — no external or plugin callers (issues
#18, #24). Its committed public surface is exactly `__all__` below: the record
dispatch API `verdict.py` consumes. Everything else here — the registry, and the
layer classes imported to build them — is implementation detail: used in-tree,
not part of the committed surface, and free to change. Tests reach the layer
classes through their own submodules (e.g. `gridfind.layers.regions`).

The engine->layer contract a layer author codes against (`Layer`, `add_cell`,
`register_structure`) is a separate surface, tracked in issue #26.
"""

from __future__ import annotations

from gridfind.engine import GridfindError, Layer
from gridfind.layers.board import GridCells
from gridfind.layers.distinct import DistinctOverGroups, boxes, cols, rows
from gridfind.layers.line_count import LineCountDistinct
from gridfind.layers.pair_sum import PairSum
from gridfind.puzzle import JsonValue, Variant

__all__ = [
    "UnknownLayerError",
    "canonical_identity",
    "expand_records",
    "resolve_records",
]


class UnknownLayerError(GridfindError):
    """A stack names a layer the registry doesn't recognize."""


LAYER_REGISTRY = {
    "board": GridCells(),
    "rows-distinct": DistinctOverGroups("rows-distinct", rows),
    "cols-distinct": DistinctOverGroups("cols-distinct", cols),
    "regions-distinct": DistinctOverGroups("regions-distinct", boxes),
    "line-count-distinct": LineCountDistinct(),
    "pair-sum": PairSum(),
}

# Sugar record types expand at load into their canonical constraint records
# (spec #45, issue #47). `sudoku` is the three basic distinct rules — board is
# not here: it comes from the Puzzle's board field, not a variant record.
SUGAR_REGISTRY: dict[str, list[str]] = {
    "sudoku": ["rows-distinct", "cols-distinct", "regions-distinct"],
}

# Param sugar: a record that renames to a canonical type and fixes one param,
# carrying its own params through. X and V are pair-sum clues whose target is
# spelled in the name — an X pair sums to 10, a V to 5 (issue #66).
PARAM_SUGAR: dict[str, tuple[str, dict[str, JsonValue]]] = {
    "x": ("pair-sum", {"sum": 10}),
    "v": ("pair-sum", {"sum": 5}),
}


def expand_records(records: tuple[Variant, ...]) -> list[Variant]:
    """Expand sugar records into their canonical constraint records — a
    load-time pass that runs before dispatch. A `{type: "sudoku"}` record
    becomes the three bare distinct records; an `{type: "x", cells}` record
    becomes a `pair-sum` carrying its cells and `sum: 10`; every other record
    passes through unchanged.
    """
    expanded: list[Variant] = []
    for record in records:
        if record.type in SUGAR_REGISTRY:
            expanded.extend(Variant(type=name) for name in SUGAR_REGISTRY[record.type])
        elif record.type in PARAM_SUGAR:
            canonical, fixed = PARAM_SUGAR[record.type]
            expanded.append(Variant(type=canonical, params={**record.params, **fixed}))
        else:
            expanded.append(record)
    return expanded


def resolve_records(records: tuple[Variant, ...]) -> list[Layer]:
    """Resolve a puzzle's variant records to layer instances: expand sugar,
    then dispatch each distinct `type` through the registry. Two records of one
    type resolve to a single layer that loops its own records (issue #65) — the
    layer, not the layer twice. An unrecognized `type` is rejected.
    """
    layers: dict[str, Layer] = {}
    for record in expand_records(records):
        if record.type not in LAYER_REGISTRY:
            msg = f"unknown variant record type {record.type!r}"
            raise UnknownLayerError(msg)
        layers.setdefault(record.type, LAYER_REGISTRY[record.type])
    return list(layers.values())


def canonical_identity(records: tuple[Variant, ...]) -> tuple[str, ...]:
    """A puzzle's identity: its expanded constraint set, alphabetically
    normalized. The sugar spelling and the explicit spelling compare equal
    (the #33 duplicate-detection rule, over records instead of a stack string).

    ponytail: keys on record `type` only — right for the sudoku family (all
    bare records). Fold params in when data-bearing variants (killer, thermo)
    land, or two cages differing only by sum would collide.
    """
    return tuple(sorted({record.type for record in expand_records(records)}))
