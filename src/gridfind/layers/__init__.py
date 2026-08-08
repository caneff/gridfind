"""Composition point for the layers package (issue #17).

Assembles the layer registry from the per-layer modules as an explicit list —
no decorator, no import-side-effect auto-discovery — and holds the constraint
dispatch API (`resolve_constraints`, `canonical_identity`, `UnknownLayerError`)
that `verdict.py` consumes.

`gridfind.layers` is **internal-only** — no external or plugin callers (issues
#18, #24). Its committed public surface is exactly `__all__` below: the constraint
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
from gridfind.layers.distinct import DistinctOverGroups, cols, regions, rows
from gridfind.layers.line_count import LineCountDistinct
from gridfind.layers.pair_sum import PairSum
from gridfind.puzzle import Constraint, JsonValue

__all__ = [
    "UnknownLayerError",
    "canonical_identity",
    "expand_constraints",
    "resolve_constraints",
]


class UnknownLayerError(GridfindError):
    """A stack names a layer the registry doesn't recognize."""


LAYER_REGISTRY = {
    "board": GridCells(),
    "rows-distinct": DistinctOverGroups("rows-distinct", rows),
    "cols-distinct": DistinctOverGroups("cols-distinct", cols),
    "regions-distinct": DistinctOverGroups("regions-distinct", regions),
    "line-count-distinct": LineCountDistinct(),
    "pair-sum": PairSum(),
}

# Sugar constraint types expand at load into their canonical constraints
# (spec #45, issue #47). `sudoku` is the three basic distinct rules — board is
# not here: it comes from the Puzzle's board field, not a constraint.
SUGAR_REGISTRY: dict[str, list[str]] = {
    "sudoku": ["rows-distinct", "cols-distinct", "regions-distinct"],
}

# Param sugar: a constraint that renames to a canonical type and fixes one
# param, carrying its own params through. X and V are pair-sum clues whose
# target is spelled in the name — an X pair sums to 10, a V to 5 (issue #66).
PARAM_SUGAR: dict[str, tuple[str, dict[str, JsonValue]]] = {
    "x": ("pair-sum", {"sum": 10}),
    "v": ("pair-sum", {"sum": 5}),
}


def expand_constraints(constraints: tuple[Constraint, ...]) -> list[Constraint]:
    """Expand sugar constraints into their canonical constraints — a load-time
    pass that runs before dispatch. A `{type: "sudoku"}` constraint becomes the
    three bare distinct constraints; an `{type: "x", cells}` constraint becomes
    a `pair-sum` carrying its cells and `sum: 10`; every other constraint
    passes through unchanged.
    """
    expanded: list[Constraint] = []
    for constraint in constraints:
        if constraint.type in SUGAR_REGISTRY:
            expanded.extend(
                Constraint(type=name) for name in SUGAR_REGISTRY[constraint.type]
            )
        elif constraint.type in PARAM_SUGAR:
            canonical, fixed = PARAM_SUGAR[constraint.type]
            expanded.append(
                Constraint(type=canonical, params={**constraint.params, **fixed})
            )
        else:
            expanded.append(constraint)
    return expanded


def resolve_constraints(constraints: tuple[Constraint, ...]) -> list[Layer]:
    """Resolve a puzzle's constraints to layer instances: expand sugar, then
    dispatch each distinct `type` through the registry. Two constraints of one
    type resolve to a single layer that loops its own constraints (issue #65) —
    the layer, not the layer twice. An unrecognized `type` is rejected.
    """
    layers: dict[str, Layer] = {}
    for constraint in expand_constraints(constraints):
        if constraint.type not in LAYER_REGISTRY:
            msg = f"unknown constraint type {constraint.type!r}"
            raise UnknownLayerError(msg)
        layers.setdefault(constraint.type, LAYER_REGISTRY[constraint.type])
    return list(layers.values())


def canonical_identity(constraints: tuple[Constraint, ...]) -> tuple[str, ...]:
    """A puzzle's identity: its expanded constraint set, alphabetically
    normalized. The sugar spelling and the explicit spelling compare equal
    (the #33 duplicate-detection rule, over constraints instead of a stack
    string).

    ponytail: keys on constraint `type` only — right for the sudoku family (all
    bare constraints). Fold params in when data-bearing variants (killer,
    thermo) land, or two cages differing only by sum would collide.
    """
    return tuple(
        sorted({constraint.type for constraint in expand_constraints(constraints)})
    )
