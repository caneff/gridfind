"""Composition point for the layers package (issue #17).

Assembles the layer registry from the per-layer modules as an explicit list —
no decorator, no import-side-effect auto-discovery — and holds the one door
from a puzzle's constraints to a layer stack (`build_stack`, `canonical_identity`,
`UnknownLayerError`) that `verdict.py` consumes (issue #101).

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

from gridfind.engine import GridfindError, Layer, MalformedPuzzleError
from gridfind.layers.board import GridCells
from gridfind.layers.cage import Cage
from gridfind.layers.distinct import (
    DistinctOverGroups,
    cols,
    regions,
    regions_from,
    rows,
)
from gridfind.layers.line_count import LineCountDistinct
from gridfind.layers.pair_difference import PairDifference
from gridfind.layers.pair_sum import PairSum
from gridfind.layers.regions import region_map_from_labels
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Constraint, JsonValue

__all__ = [
    "UnknownLayerError",
    "build_stack",
    "canonical_identity",
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
    "pair-difference": PairDifference(),
    "schrodinger": Schrodinger(),
    "cage": Cage(),
}

# Two mechanisms expand a constraint at load (spec #45, issue #47), and they
# are not the same shape — one type becoming many is a preset, one type
# becoming another is an alias.
#
# A **preset** is the decided word for a named, reusable bundle (CONTEXT.md):
# `sudoku` is the three basic distinct rules. Board is not here — it comes
# from the Puzzle's board field, not a constraint.
PRESET_REGISTRY: dict[str, list[str]] = {
    "sudoku": ["rows-distinct", "cols-distinct", "regions-distinct"],
}

# An **alias** renames one type to another and fixes one param, carrying its
# own params through. X and V are pair-sum clues whose target is spelled in
# the name — an X pair sums to 10, a V to 5 (issue #66).
ALIAS_REGISTRY: dict[str, tuple[str, dict[str, JsonValue]]] = {
    "x": ("pair-sum", {"sum": 10}),
    "v": ("pair-sum", {"sum": 5}),
}


def expand_constraints(constraints: tuple[Constraint, ...]) -> list[Constraint]:
    """Expand presets and aliases into canonical constraints — a load-time
    pass that runs before dispatch. A `{type: "sudoku"}` constraint is a
    preset and becomes the three bare distinct constraints; an
    `{type: "x", cells}` constraint is an alias and becomes a `pair-sum`
    carrying its cells and `sum: 10`; every other constraint passes through
    unchanged.

    An alias refuses a constraint that also states a param the alias itself
    fixes — an X clue naming its own sum is a contradiction, not a value to
    silently overwrite. A param the alias does not fix (a clue's cells) passes
    through untouched.
    """
    expanded: list[Constraint] = []
    for constraint in constraints:
        if constraint.type in PRESET_REGISTRY:
            expanded.extend(
                Constraint(type=name) for name in PRESET_REGISTRY[constraint.type]
            )
        elif constraint.type in ALIAS_REGISTRY:
            canonical, fixed = ALIAS_REGISTRY[constraint.type]
            conflicts = sorted(set(constraint.params) & set(fixed))
            if conflicts:
                msg = (
                    f"{constraint.type!r} alias fixes {conflicts[0]!r}; "
                    "the puzzle may not also state it"
                )
                raise MalformedPuzzleError(msg)
            expanded.append(
                Constraint(type=canonical, params={**constraint.params, **fixed})
            )
        else:
            expanded.append(constraint)
    return expanded


def build_stack(
    constraints: tuple[Constraint, ...],
    *,
    size: int,
) -> tuple[list[Constraint], list[Layer]]:
    """The one door from a puzzle's constraints to its layer stack (issue
    #101): expand presets and aliases exactly once, then dispatch each
    distinct canonical `type` through the registry, and return both the
    canonical constraints and the resulting stack.

    The compulsory `board` layer is seeded into the stack before dispatch, so
    a puzzle that also names `board` as a constraint dedups onto that same
    entry rather than registering the grid a second time — `board` is not a
    constraint (its grid comes from the puzzle's own board field), but a
    setter naming it anyway costs one layer, not two.

    Two constraints of one type otherwise resolve to a single layer that loops
    its own constraints (issue #65) — the layer, not the layer twice. An
    unrecognized `type` is rejected.

    A `regions-distinct` constraint carrying `params["regions"]` (issue #123)
    is the one type-directed exception: the door reads the setter's flat
    label matrix, validates and converts it to a `RegionMap` (`size` is why
    this door takes one — the matrix shape check needs it), and builds a
    fresh `DistinctOverGroups` closed over that partition instead of
    dispatching to the registry's box-tiling default. The layer itself stays
    param-agnostic; only the function it is built with differs.
    """
    canonical = expand_constraints(constraints)
    layers: dict[str, Layer] = {"board": LAYER_REGISTRY["board"]}
    for constraint in canonical:
        if constraint.type not in LAYER_REGISTRY:
            msg = f"unknown constraint type {constraint.type!r}"
            raise UnknownLayerError(msg)
        if constraint.type == "regions-distinct" and "regions" in constraint.params:
            region_map = region_map_from_labels(size, constraint.params["regions"])
            layers[constraint.type] = DistinctOverGroups(
                constraint.type, regions_from(region_map)
            )
        else:
            layers.setdefault(constraint.type, LAYER_REGISTRY[constraint.type])
    return canonical, list(layers.values())


def canonical_identity(constraints: tuple[Constraint, ...]) -> tuple[str, ...]:
    """A puzzle's identity: its expanded constraint set, alphabetically
    normalized. The preset spelling and the explicit spelling compare equal
    (the #33 duplicate-detection rule, over constraints instead of a stack
    string).

    ponytail: keys on constraint `type` only — right for the sudoku family (all
    bare constraints). Killer cages (issue #196) already collide on this: two
    cages differing only by `value` compare identical here. Left alone —
    `canonical_identity` has zero non-test callers, and the same collision
    already existed for cage `cells` before the sum landed, so folding only
    `value` in would be an inconsistent half-fix for a consumer that doesn't
    exist yet. Fold params in (thermo too) when a real caller needs it.
    """
    return tuple(
        sorted({constraint.type for constraint in expand_constraints(constraints)})
    )
