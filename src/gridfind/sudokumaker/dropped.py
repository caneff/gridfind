"""The drop policy for constraints `DECODER_REGISTRY` does not model:
`warn_on_dropped_constraints` (the loud/quiet drop decision), `has_live_data`
(the shared active/inert predicate it and `scripts/inspect_link.py` both call),
and `constraint_name` (a custom constraint's display name). Imports only the
public `DECODER_REGISTRY` from `registry` — the dispatch table this policy
reads as the already-modeled ruleset, not the decoder internals that build it.
"""

from __future__ import annotations

import sys
from typing import Any, cast

from gridfind.sudokumaker.naming import named_component, shape_needs_cells
from gridfind.sudokumaker.registry import DECODER_REGISTRY
from gridfind.sudokumaker.wire_types import (
    ANTI_KING_TYPE,
    ANTI_KNIGHT_TYPE,
    NEGATIVE_DIAGONAL_TYPE,
    POSITIVE_DIAGONAL_TYPE,
)

# The union of every registered type's live-data keys, order-preserved and
# deduped — `has_live_data` checks these instead of a hand-copied list that
# happened to match what the decoders in `registry` read.
_LIVE_LIST_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys(key for entry in DECODER_REGISTRY.values() for key in entry.live_keys)
)

# Global toggles carry their rule in the bare type, not a payload, so
# `has_live_data` can't read their liveness off a `live_keys` list the way it
# does for clue/cage blocks — an enabled toggle's presence is the live rule.
# The coverage-floor E2E gate turns red if a toggle row is added to the
# registry without listing it here, so the two never drift.
_TOGGLE_WIRE_TYPES = frozenset(
    {
        NEGATIVE_DIAGONAL_TYPE,
        POSITIVE_DIAGONAL_TYPE,
        ANTI_KING_TYPE,
        ANTI_KNIGHT_TYPE,
    }
)


def _carrier_supplies_cage_cells(constraint: dict[str, Any]) -> bool:
    """True when `constraint` itself carries a `cages` list naming cells — the
    payload a cage-selector/cell-marker name needs (`naming.shape_needs_cells`).
    `type 2001`/`type 301` blocks carry this; a `type 1000` custom constraint's
    payload lives under `input.groups` instead, so it never does."""
    cages = constraint.get("cages")
    return isinstance(cages, list) and any(
        isinstance(cage, dict) and cage.get("cells") for cage in cages
    )


def warn_on_dropped_constraints(puzzle_data: dict[str, object]) -> None:
    """Ignore every constraint gridfind doesn't model, warning to
    stderr for any that carries live data — so a verdict is never silently
    computed under a smaller ruleset than the link states.

    Types in `DECODER_REGISTRY` — 0 givens, 1 regions, 200
    white-kropki, 201 black-kropki, 202 XV, 300 thermo, 301 killer-cage, 2001
    cosmetic-cage — are modeled elsewhere and pass through. A `disabled`
    constraint is skipped first with no warning: the setter switched it off,
    so it is not part of
    the puzzle even for a type gridfind knows how to decode. A remaining
    enabled unmodeled constraint whose `definition.name` names a `global-flag`
    component (`naming.named_component`) — `Somedoku`, so
    far — passes through untouched regardless of its own payload: the
    component needs no cells, so it is never a misplaced declaration, and it
    is recognized and decoded elsewhere (`global_flags.has_somedoku_component`),
    not dropped. One naming a cage-selector/cell-marker component
    instead, whose shape needs a cage's cells the constraint doesn't carry
    (`_carrier_supplies_cage_cells`), is a misplaced declaration — dropped
    loudly, naming the component, regardless of whether its own payload would
    otherwise read as live. Any other unmodeled constraint is inert (empty or
    cosmetic-only payload) and dropped quietly, or active (a live
    clue/negative list or a populated group) and dropped loudly, named by its
    `definition.name` when the link carries one. Honoring a specific variant
    rather than dropping it is the opt-in variant-decoder path — the kropki
    and XV decoders take it for their own `negative` list, enforcing it
    instead of dropping it.

    `has_live_data` is the shared active/inert predicate: this runtime policy
    and `scripts/inspect_link.py`'s `classify_constraint` both
    call it, so the dev tool's report and what the decoder actually drops can
    never disagree."""
    constraints = puzzle_data.get("constraints", [])
    if not isinstance(constraints, list):
        return
    for raw_constraint in constraints:
        if not isinstance(raw_constraint, dict):
            continue
        constraint = cast("dict[str, Any]", raw_constraint)
        if constraint.get("disabled") is True:
            continue
        kind = constraint.get("type")
        if kind in DECODER_REGISTRY:
            continue
        name = constraint_name(constraint)
        component = named_component(name)
        if component is not None and not shape_needs_cells(component.shape):
            continue
        if component is not None and not _carrier_supplies_cage_cells(constraint):
            msg = (
                f"warning: ignoring {name!r} (type {kind!r}) — its "
                f"{component.shape} name needs a cage's cells, which this "
                "constraint does not carry — verdict computed without it"
            )
            print(msg, file=sys.stderr)
            continue
        if has_live_data(constraint):
            named = f" {name!r}" if name is not None else ""
            msg = (
                f"warning: ignoring unmodeled constraint{named} (type {kind!r}) "
                "— verdict computed without it"
            )
            print(msg, file=sys.stderr)


def has_live_data(constraint: dict[str, Any]) -> bool:
    """True when a constraint carries a rule gridfind would honour: a global
    toggle (anti-knight, anti-king, a diagonal), whose bare enabled presence is
    the rule; a non-empty list under one of `DECODER_REGISTRY`'s `live_keys`
    (`clues`/`negative`/`cages`); or a group holding real cells under
    `input.groups`. Empty payloads and cosmetic-only `lines` are inert.

    `cages` is a killer-cage block's (`type 301`) payload. It is decoded now,
    so `warn_on_dropped_constraints` skips it — this entry marks
    a populated cage block `active` for `scripts/inspect_link.py`, exactly as
    the `clues` entry does for decoded XV (`type 202`): a decoded variant still
    carries a live rule the dev tool must not report as inert. A `type 2001`
    cosmetic cage carries its cages under the same `cages` key, so a populated
    cosmetic block is `active` on the same scan.

    Public so `scripts/inspect_link.py` classifies constraints against the same
    predicate the decoder drops by. `Any` keeps the decoded-JSON
    boundary type (a dict narrowed from the untyped payload), as `link_to_puzzle`
    does for `puzzle_data`."""
    if constraint.get("type") in _TOGGLE_WIRE_TYPES:
        return True
    for key in _LIVE_LIST_KEYS:
        value = constraint.get(key)
        if isinstance(value, list) and value:
            return True
    payload = constraint.get("input")
    if isinstance(payload, dict):
        groups = payload.get("groups")
        if isinstance(groups, list) and any(
            isinstance(group, dict) and group.get("cells") for group in groups
        ):
            return True
    return False


def constraint_name(constraint: dict[str, Any]) -> str | None:
    """A custom constraint's display name (e.g. "Same Difference Lines"), read
    from `definition.name` — the field SudokuMaker stores it under. `None` when the link
    carries no name for the type. Public alongside
    `has_live_data` for `scripts/inspect_link.py`."""
    definition = constraint.get("definition")
    if isinstance(definition, dict):
        name = definition.get("name")
        if isinstance(name, str):
            return name
    return None
