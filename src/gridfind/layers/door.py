"""The one door from a puzzle's constraints to a layer stack.

Assembles the layer registry from the per-layer modules as an explicit list —
no decorator, no import-side-effect auto-discovery — and holds `build_stack`,
the seam `verdict.py` consumes, and `UnknownLayerError`, the refusal it
raises for a constraint type no layer claims.

`LAYER_REGISTRY`, `PRESET_REGISTRY`, and `ALIAS_REGISTRY` are implementation
detail: used in-tree (and, for `ALIAS_REGISTRY`, by
`sudokumaker.edge_clues`), not part of the package's committed surface
(`gridfind.layers.__all__`). Tests reach the layer classes through their own
submodules (e.g. `gridfind.layers.regions`).
"""

from __future__ import annotations

from typing import cast

from gridfind.engine import GridfindError, Layer, MalformedPuzzleError
from gridfind.layers.arrow import Arrow
from gridfind.layers.board import GridCells
from gridfind.layers.cage import Cage
from gridfind.layers.clone import Clone
from gridfind.layers.constant_modifier import ConstantModifier
from gridfind.layers.distinct import (
    DistinctOverGroups,
    cols,
    disjoint_groups_from,
    extra_regions_from,
    negative_diagonal,
    positive_diagonal,
    regions,
    regions_from,
    rows,
)
from gridfind.layers.doubler import Doubler
from gridfind.layers.equality_cage import EqualityCage
from gridfind.layers.group_sum import GroupSum
from gridfind.layers.indexing import Indexing
from gridfind.layers.line import Line
from gridfind.layers.line_count import LineCountDistinct
from gridfind.layers.numbered_rooms import NumberedRooms
from gridfind.layers.offset_adjacency import (
    KING_OFFSETS,
    KNIGHT_OFFSETS,
    ORTHOGONAL_OFFSETS,
    OffsetAdjacency,
    OffsetValueGap,
)
from gridfind.layers.outside_cells import OutsideCells
from gridfind.layers.pair_difference import differs_by
from gridfind.layers.pair_ratio import ratio_of
from gridfind.layers.pair_relation import PairRelation
from gridfind.layers.parity import Parity
from gridfind.layers.quadruple import Quadruple
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
    "outside-cells": OutsideCells(),
    "rows-distinct": DistinctOverGroups("rows-distinct", rows),
    "cols-distinct": DistinctOverGroups("cols-distinct", cols),
    "regions-distinct": DistinctOverGroups("regions-distinct", regions),
    "negative-diagonal": DistinctOverGroups("negative-diagonal", negative_diagonal),
    "positive-diagonal": DistinctOverGroups("positive-diagonal", positive_diagonal),
    "line-count-distinct": LineCountDistinct(),
    "anti-knight": OffsetAdjacency("anti-knight", KNIGHT_OFFSETS),
    "anti-king": OffsetAdjacency("anti-king", KING_OFFSETS),
    "nonconsecutive": OffsetValueGap("nonconsecutive", ORTHOGONAL_OFFSETS),
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
    "line": Line(),
    "indexing": Indexing(),
    "parity": Parity(),
    "numbered-rooms": NumberedRooms(),
    "quadruple": Quadruple(),
    "clone": Clone(),
    "arrow": Arrow(),
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


def _type_directed_layer(constraint: Constraint, size: int) -> Layer | None:
    """A constraint type whose layer needs data beyond its own bare presence,
    built fresh rather than taken from the registry's shared default. `None`
    when `constraint` needs no special handling, so `build_stack` falls
    through to that default.

    Two cases, both param-agnostic (only the instance the door builds them
    with differs): a `regions-distinct` constraint carrying
    `params["regions"]` resolves through the shared
    `region_map_for_constraints` rather than re-deriving the jigsaw-vs-box
    branch inline, and builds a fresh `DistinctOverGroups` closed over that
    partition; a `constant` constraint carrying `params["value"]` builds a
    fresh `ConstantModifier(value=k)` instead of dispatching to the
    registry's `k = 0` nullifier default (ADR-0016). `extra-region` is directed
    too but aggregates every window at once, so it has its own builder
    (`_extra_region_layer`) rather than this per-constraint one.
    """
    if constraint.type == "regions-distinct" and "regions" in constraint.params:
        region_map = region_map_for_constraints([constraint], size)
        return DistinctOverGroups(constraint.type, regions_from(region_map))
    if constraint.type == "constant" and "value" in constraint.params:
        value = cast("int", constraint.params["value"])
        return ConstantModifier(value=value)
    return None


def _extra_region_layer(constraints: list[Constraint]) -> DistinctOverGroups | None:
    """The `type 305` windoku windows folded into one `DistinctOverGroups`:
    each block's cells one group of a single combined partition, so several
    windows never overwrite one another through the type-keyed layer dedup.
    `None` when the puzzle draws no extra region. Aggregated
    across all `extra-region` constraints at once — unlike `regions-distinct`,
    whose one partition rides a single constraint — so it cannot go through the
    per-constraint `_type_directed_layer`.
    """
    blocks = [
        cast("list[str]", constraint.params["cells"])
        for constraint in constraints
        if constraint.type == "extra-region"
    ]
    if not blocks:
        return None
    return DistinctOverGroups("extra-region", extra_regions_from(blocks))


def _disjoint_groups_layer(
    constraints: list[Constraint], size: int
) -> DistinctOverGroups | None:
    """`disjoint-groups`'s partition needs the puzzle's own region map, not
    just its own bare presence, so — like `extra-region` — it is aggregated
    here rather than routed through the per-constraint `_type_directed_layer`.
    `None` when the puzzle draws no `disjoint-groups` constraint at all.

    A `disjoint-groups` constraint with no sibling `regions-distinct` would
    otherwise fall through `region_map_for_constraints`'s own whole-board
    fallback — one region covering everything, which transposes into
    `size*size` groups of one cell each, a silent no-op — so that absence is
    refused here instead of quietly accepted.
    """
    if not any(constraint.type == "disjoint-groups" for constraint in constraints):
        return None
    if not any(constraint.type == "regions-distinct" for constraint in constraints):
        msg = "disjoint-groups needs a regions-distinct constraint; none is present"
        raise MalformedPuzzleError(msg)
    region_map = region_map_for_constraints(constraints, size)
    return DistinctOverGroups("disjoint-groups", disjoint_groups_from(region_map))


def build_stack(
    constraints: tuple[Constraint, ...],
    *,
    size: int,
) -> tuple[list[Constraint], list[Layer]]:
    """The one door from a puzzle's constraints to its layer stack: expand presets and
    aliases exactly once, then dispatch each
    distinct canonical `type` through the registry, and return both the
    canonical constraints and the resulting stack.

    The compulsory `board` and `outside-cells` layers are seeded into the
    stack before dispatch, so a puzzle that also names `board` as a
    constraint dedups onto that same entry rather than registering the grid a
    second time — `board` is not a constraint (its grid comes from the
    puzzle's own board field), but a setter naming it anyway costs one layer,
    not two. `outside-cells` carries no constraint of its own either: it
    stands ready to register any border address a decoration or clue names in
    its own `params["cells"]`, empty or not.

    Two constraints of one type otherwise resolve to a single layer that loops
    its own constraints — the layer, not the layer twice. An
    unrecognized `type` is rejected.

    `_type_directed_layer` names the constraint types whose layer needs more
    than its own bare presence to build (`regions-distinct`, `constant`);
    everything else falls to `setdefault` below, returning the registry's one
    shared instance. The bare, no-param case of
    `regions-distinct`/`constant` — no `params["regions"]`/`params["value"]`
    — is left to that same `setdefault` rather than also routed through the
    helper: it must keep returning the registry's one shared instance (tests
    key off that identity for `regions-distinct`; `constant`'s shared
    instance is already the `k = 0` default the helper would otherwise
    rebuild). `extra-region` and `disjoint-groups` are directed too but each
    aggregate across the whole constraint list rather than dispatching per
    constraint, so they carry their own builders
    (`_extra_region_layer`/`_disjoint_groups_layer`) seeded before the loop.
    """
    canonical = expand_constraints(constraints)
    layers: dict[str, Layer] = {
        "board": LAYER_REGISTRY["board"],
        "outside-cells": LAYER_REGISTRY["outside-cells"],
    }
    extra_region = _extra_region_layer(canonical)
    if extra_region is not None:
        layers["extra-region"] = extra_region
    disjoint_groups = _disjoint_groups_layer(canonical, size)
    if disjoint_groups is not None:
        layers["disjoint-groups"] = disjoint_groups
    for constraint in canonical:
        if constraint.type in ("extra-region", "disjoint-groups"):
            continue  # already folded into one layer by their own builder above
        if constraint.type not in LAYER_REGISTRY:
            msg = f"unknown constraint type {constraint.type!r}"
            raise UnknownLayerError(msg)
        override = _type_directed_layer(constraint, size)
        if override is not None:
            layers[constraint.type] = override
        else:
            layers.setdefault(constraint.type, LAYER_REGISTRY[constraint.type])
    refuse_s_blind_over_widening(layers)
    return canonical, list(layers.values())
