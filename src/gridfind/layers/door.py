"""The one door from a puzzle's constraints to a layer stack.

Assembles the layer registry from the per-layer modules as an explicit list —
no decorator, no import-side-effect auto-discovery — and holds `build_stack`
and `UnknownLayerError`, the seam `verdict.py` consumes.

`LAYER_REGISTRY`, `PRESET_REGISTRY`, and `ALIAS_REGISTRY` are implementation
detail: used in-tree (and, for `ALIAS_REGISTRY`, by
`sudokumaker.edge_clues`), not part of the package's committed surface
(`gridfind.layers.__all__`). Tests reach the layer classes through their own
submodules (e.g. `gridfind.layers.regions`).
"""

from __future__ import annotations

from typing import cast

from gridfind.engine import GridfindError, Layer, MalformedPuzzleError
from gridfind.layers.board import GridCells
from gridfind.layers.cage import Cage
from gridfind.layers.constant_modifier import ConstantModifier
from gridfind.layers.distinct import (
    DistinctOverGroups,
    cols,
    negative_diagonal,
    positive_diagonal,
    regions,
    regions_from,
    rows,
)
from gridfind.layers.doubler import Doubler
from gridfind.layers.equality_cage import EqualityCage
from gridfind.layers.group_sum import GroupSum
from gridfind.layers.line_count import LineCountDistinct
from gridfind.layers.offset_adjacency import (
    KING_OFFSETS,
    KNIGHT_OFFSETS,
    OffsetAdjacency,
)
from gridfind.layers.pair_difference import differs_by
from gridfind.layers.pair_ratio import ratio_of
from gridfind.layers.pair_relation import PairRelation
from gridfind.layers.regions import region_map_for_constraints
from gridfind.layers.rellik_cage import RellikCage
from gridfind.layers.s_blind import refuse_s_blind_over_widening
from gridfind.layers.schrodinger import Schrodinger
from gridfind.layers.thermo import Thermo
from gridfind.puzzle import Constraint, JsonValue


class UnknownLayerError(GridfindError):
    """A stack names a layer the registry doesn't recognize."""


LAYER_REGISTRY = {
    "board": GridCells(),
    "rows-distinct": DistinctOverGroups("rows-distinct", rows),
    "cols-distinct": DistinctOverGroups("cols-distinct", cols),
    "regions-distinct": DistinctOverGroups("regions-distinct", regions),
    "negative-diagonal": DistinctOverGroups("negative-diagonal", negative_diagonal),
    "positive-diagonal": DistinctOverGroups("positive-diagonal", positive_diagonal),
    "line-count-distinct": LineCountDistinct(),
    "anti-knight": OffsetAdjacency("anti-knight", KNIGHT_OFFSETS),
    "anti-king": OffsetAdjacency("anti-king", KING_OFFSETS),
    "pair-difference": PairRelation("pair-difference", relation=differs_by),
    "pair-ratio": PairRelation("pair-ratio", relation=ratio_of),
    "schrodinger": Schrodinger(),
    "cage": Cage(),
    "doubler": Doubler(),
    "constant": ConstantModifier(),
    "group-sum": GroupSum(),
    "rellik-cage": RellikCage(),
    "equality-cage": EqualityCage(),
    "thermo": Thermo(),
}

# Two mechanisms expand a constraint at load, and they
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
# own params through. X and V are group-sum clues whose target is spelled in
# the name — an X pair sums to 10, a V to 5.
ALIAS_REGISTRY: dict[str, tuple[str, dict[str, JsonValue]]] = {
    "x": ("group-sum", {"sum": 10}),
    "v": ("group-sum", {"sum": 5}),
}


def expand_constraints(constraints: tuple[Constraint, ...]) -> list[Constraint]:
    """Expand presets and aliases into canonical constraints — a load-time
    pass that runs before dispatch. A `{type: "sudoku"}` constraint is a
    preset and becomes the three bare distinct constraints; an
    `{type: "x", cells}` constraint is an alias and becomes a `group-sum`
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
    """The one door from a puzzle's constraints to its layer stack: expand presets and
    aliases exactly once, then dispatch each
    distinct canonical `type` through the registry, and return both the
    canonical constraints and the resulting stack.

    The compulsory `board` layer is seeded into the stack before dispatch, so
    a puzzle that also names `board` as a constraint dedups onto that same
    entry rather than registering the grid a second time — `board` is not a
    constraint (its grid comes from the puzzle's own board field), but a
    setter naming it anyway costs one layer, not two.

    Two constraints of one type otherwise resolve to a single layer that loops
    its own constraints — the layer, not the layer twice. An
    unrecognized `type` is rejected.

    A `regions-distinct` constraint carrying `params["regions"]`, and a
    `constant` constraint carrying `params["value"]`, are the two
    type-directed exceptions: `regions-distinct` resolves through the shared
    `region_map_for_constraints` rather than re-deriving the jigsaw-vs-box
    branch inline, and builds a fresh `DistinctOverGroups` closed over that
    partition; `constant` builds a fresh `ConstantModifier(value=k)` instead
    of dispatching to the registry's `k = 0` nullifier default (ADR-0016).
    Both layers stay param-agnostic; only the instance the door builds them
    with differs.

    The bare, no-param case of either — `regions-distinct` with no
    `params["regions"]`, `constant` with no `params["value"]` — is left to
    `setdefault` below rather than also routed through its special case: it
    must keep returning the registry's one shared instance (tests key off
    that identity for `regions-distinct`; `constant`'s shared instance is
    already the `k = 0` default the special case would otherwise rebuild).
    """
    canonical = expand_constraints(constraints)
    layers: dict[str, Layer] = {"board": LAYER_REGISTRY["board"]}
    for constraint in canonical:
        if constraint.type not in LAYER_REGISTRY:
            msg = f"unknown constraint type {constraint.type!r}"
            raise UnknownLayerError(msg)
        if constraint.type == "regions-distinct" and "regions" in constraint.params:
            region_map = region_map_for_constraints([constraint], size)
            layers[constraint.type] = DistinctOverGroups(
                constraint.type, regions_from(region_map)
            )
        elif constraint.type == "constant" and "value" in constraint.params:
            value = cast("int", constraint.params["value"])
            layers[constraint.type] = ConstantModifier(value=value)
        else:
            layers.setdefault(constraint.type, LAYER_REGISTRY[constraint.type])
    refuse_s_blind_over_widening(layers)
    return canonical, list(layers.values())
