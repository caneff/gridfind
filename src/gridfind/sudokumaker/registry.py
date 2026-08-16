"""`DECODER_REGISTRY`: the one table wire-type -> (handler, live-data payload
keys, display name, setter-facing doc) that `decode_link` dispatches through,
`warn_on_dropped_constraints` treats as the already-modeled ruleset, and
`has_live_data` reads `live_keys` from. Also the global-toggle types
(anti-knight, anti-king, the two diagonals) and their shared handler factory
`_global_toggle_handler` — bare enabled-presence-is-the-rule blocks that exist
only to feed rows into this registry, so they're defined alongside it rather
than given their own module.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.cages import cage_constraints, thermo_constraints
from gridfind.sudokumaker.edge_clues import (
    black_kropki_constraints,
    kropki_constraints,
    xv_constraints,
)
from gridfind.sudokumaker.naming import named_component, shape_needs_cells
from gridfind.sudokumaker.regions import regions_constraints
from gridfind.sudokumaker.wire_types import (
    ANTI_KING_TYPE,
    ANTI_KNIGHT_TYPE,
    CAGE_TYPE,
    COSMETIC_CAGE_TYPE,
    KROPKI_BLACK_TYPE,
    KROPKI_WHITE_TYPE,
    NEGATIVE_DIAGONAL_TYPE,
    POSITIVE_DIAGONAL_TYPE,
    THERMO_TYPE,
    XV_TYPE,
)


def _global_toggle_handler(
    wire_type: int, constraint_type: str
) -> Callable[[ConstraintBuckets, int], list[Constraint]]:
    """A decoder for a bare global-toggle block (anti-knight, anti-king, a
    single diagonal): the block carries no payload — its enabled presence is
    the whole rule — so any enabled block of `wire_type` stands up
    `constraint_type` once, and a cosmetic `style` on the block is ignored. A
    `disabled` block contributes nothing (the setter switched the rule off)."""

    def handler(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
        for _ in enabled_blocks(buckets, wire_type):
            return [Constraint(constraint_type)]
        return []

    return handler


@dataclass(frozen=True)
class SetterDoc:
    """The setter-facing facts a `DECODER_REGISTRY` row owes the accepted-link
    setter guide (ADR-0013): the display name a setter recognizes, the wire
    block gridfind reads, what it decodes to, and its accept/ignore/reject
    verdict. Sourced from `docs/research/accepted-link-constraint-map.md` §3
    — the SudokuMaker draw-action itself is deliberately absent; ADR-0013
    keeps it in the page template instead."""

    display_name: str
    wire_block: str
    decode_result: str
    verdict: str


@dataclass(frozen=True)
class DecodedType:
    """One SudokuMaker wire-type the decoder recognizes, one row wide: `handler` builds
    this type's `Constraint`s from the link (`None` for a type with nothing to
    build through `decode_link`'s generic dispatch — a bare `type 0` is just
    the unconditional rows/cols, and `type 2001` cosmetic cages are dispatched
    by hand for their richer `_CosmeticCageDecode` return; `type 1`'s regions
    live behind
    `regions_constraints` like every other generically-dispatched handler),
    `live_keys` are the payload keys that mark this type's wire shape as
    carrying a real rule (read by `has_live_data`, generalized to unmodeled
    types too), `name` labels it in the decoder's own warnings, and
    `setter_doc` carries the setter-facing reference-table facts for this
    type — `None` for a structural row (`type 0`/`type 1`) that no setter
    draws directly."""

    handler: Callable[[ConstraintBuckets, int], list[Constraint]] | None
    live_keys: tuple[str, ...]
    name: str
    setter_doc: SetterDoc | None


# The one table wire-type -> (handler, live-data payload keys, display name):
# `decode_link` dispatches through it, `warn_on_dropped_constraints` treats
# its keys as the already-modeled ruleset, and `has_live_data` reads its
# `live_keys` — adding a link type is one row here, not three hand-synced
# call sites.
DECODER_REGISTRY: dict[int, DecodedType] = {
    0: DecodedType(handler=None, live_keys=(), name="givens", setter_doc=None),
    1: DecodedType(
        handler=regions_constraints, live_keys=(), name="regions", setter_doc=None
    ),
    KROPKI_WHITE_TYPE: DecodedType(
        handler=kropki_constraints,
        live_keys=("clues", "negative"),
        name="white-kropki",
        setter_doc=SetterDoc(
            display_name="White Kropki (Difference Dot)",
            wire_block="type 200 {clues:[{value, edge}], negative:[…]}",
            decode_result="One pair-difference Constraint per clue; value maps"
            " verbatim to diff.",
            verdict="Accept the positive clues. A non-empty negative list is"
            " warn-and-dropped to stderr. An edge naming no in-bounds pair"
            " raises ValueError. disabled blocks are skipped.",
        ),
    ),
    KROPKI_BLACK_TYPE: DecodedType(
        handler=black_kropki_constraints,
        live_keys=("clues", "negative"),
        name="black-kropki",
        setter_doc=SetterDoc(
            display_name="Black Kropki (Ratio Dot)",
            wire_block="type 201 {clues:[{value, edge}], negative:[…]} —"
            " same shape as white kropki.",
            decode_result="One pair-ratio Constraint per clue; value maps"
            " verbatim to k.",
            verdict="Accept the positive clues; negative is warn-and-dropped."
            " A non-integer value raises ValueError, as does an out-of-range"
            " edge. disabled blocks are skipped.",
        ),
    ),
    XV_TYPE: DecodedType(
        handler=xv_constraints,
        live_keys=("clues", "negative"),
        name="XV",
        setter_doc=SetterDoc(
            display_name="XV",
            wire_block="type 202 {clues:[{value, edge}], negative:[…]} —"
            " value is 10 (X) or 5 (V).",
            decode_result="One aliased group-sum Constraint per clue: 10"
            " selects the X alias, 5 the V alias.",
            verdict="Accept clues whose value is 10 or 5; any other value"
            " raises ValueError. negative is warn-and-dropped; disabled"
            " blocks are skipped.",
        ),
    ),
    CAGE_TYPE: DecodedType(
        handler=cage_constraints,
        live_keys=("cages",),
        name="killer-cage",
        setter_doc=SetterDoc(
            display_name="Killer Cage",
            wire_block="type 301 {cages:[{cells, value}]}.",
            decode_result="Each cage becomes a no-repeats cage Constraint;"
            " a positive value additionally emits a group-sum over the same"
            " cells.",
            verdict="Accept. value 0 or absent is SudokuMaker's own no-sum"
            " cage — cage alone, no group-sum. disabled blocks are skipped;"
            " an empty cages list adds nothing.",
        ),
    ),
    COSMETIC_CAGE_TYPE: DecodedType(
        handler=None,
        live_keys=("cages",),
        name="cosmetic-cage",
        setter_doc=SetterDoc(
            display_name="Cosmetic Cage",
            wire_block="type 2001 {cages:[{value:str, cells}], name?,"
            " style?} — value is a string; a top-level name may mark the"
            " block as a variant declaration.",
            decode_result="name classifies the block: Sum/Killer decodes as a"
            " killer cage (a numeric non-zero string value graduates to a"
            " group-sum); Doubler emits per-cell modifier directives;"
            " S-cell/Schrödinger/Schrodinger infers Schrödinger-ness and"
            " routes its cells through the per-cell S-cell branch; absent or"
            " unrecognized carries no rule.",
            verdict="Accept a recognized name. An unnamed or unrecognized"
            " name is warn-and-dropped to stderr, naming the block."
            " disabled blocks are skipped.",
        ),
    ),
    THERMO_TYPE: DecodedType(
        handler=thermo_constraints,
        live_keys=("thermometers",),
        name="thermo",
        setter_doc=SetterDoc(
            display_name="Thermometer",
            wire_block="type 300 {slow:bool, thermometers:[[cell indices,"
            " bulb first], …]}.",
            decode_result="One thermo Constraint per path, order preserved"
            " (bulb first); slow rides onto every path in the block.",
            verdict="Accept. disabled blocks are skipped; an empty"
            " thermometers list adds nothing.",
        ),
    ),
    NEGATIVE_DIAGONAL_TYPE: DecodedType(
        handler=_global_toggle_handler(NEGATIVE_DIAGONAL_TYPE, "negative-diagonal"),
        live_keys=(),
        name="negative-diagonal",
        setter_doc=SetterDoc(
            display_name="Negative Diagonal (\\)",
            wire_block="type 10 {style?} — a bare toggle; style is cosmetic.",
            decode_result="One negative-diagonal Constraint: the `\\` diagonal"
            " holds all-different digits. Independent of the positive diagonal.",
            verdict="Accept an enabled block. A disabled block is skipped; the"
            " cosmetic style is ignored.",
        ),
    ),
    POSITIVE_DIAGONAL_TYPE: DecodedType(
        handler=_global_toggle_handler(POSITIVE_DIAGONAL_TYPE, "positive-diagonal"),
        live_keys=(),
        name="positive-diagonal",
        setter_doc=SetterDoc(
            display_name="Positive Diagonal (/)",
            wire_block="type 11 {style?} — a bare toggle; style is cosmetic.",
            decode_result="One positive-diagonal Constraint: the `/` diagonal"
            " holds all-different digits. Both toggles together are X-sudoku.",
            verdict="Accept an enabled block. A disabled block is skipped; the"
            " cosmetic style is ignored.",
        ),
    ),
    ANTI_KING_TYPE: DecodedType(
        handler=_global_toggle_handler(ANTI_KING_TYPE, "anti-king"),
        live_keys=(),
        name="anti-king",
        setter_doc=SetterDoc(
            display_name="Anti-King",
            wire_block="type 12 — a bare toggle, no payload.",
            decode_result="One anti-king Constraint: no two cells a king's step"
            " apart share a digit.",
            verdict="Accept an enabled block. A disabled block is skipped.",
        ),
    ),
    ANTI_KNIGHT_TYPE: DecodedType(
        handler=_global_toggle_handler(ANTI_KNIGHT_TYPE, "anti-knight"),
        live_keys=(),
        name="anti-knight",
        setter_doc=SetterDoc(
            display_name="Anti-Knight",
            wire_block="type 13 — a bare toggle, no payload.",
            decode_result="One anti-knight Constraint: no two cells a knight's"
            " hop apart share a digit.",
            verdict="Accept an enabled block. A disabled block is skipped.",
        ),
    ),
}

# The union of every registered type's live-data keys, order-preserved and
# deduped — `has_live_data` checks these instead of a hand-copied list that
# happened to match what the decoders above read.
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


def _carrier_supplies_cage_cells(constraint: dict[Any, Any]) -> bool:
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
    component (`naming.named_component`, spec #431/#436) — `Somedoku`, so
    far — passes through untouched regardless of its own payload: the
    component needs no cells, so it is never a misplaced declaration, and it
    is recognized and decoded elsewhere (`global_flags.has_somedoku_component`),
    not dropped. One naming a cage-selector/cell-marker component (#434)
    instead, whose shape needs a cage's cells the constraint doesn't carry
    (`_carrier_supplies_cage_cells`), is a misplaced declaration — dropped
    loudly, naming the component, regardless of whether its own payload would
    otherwise read as live. Any other unmodeled constraint is inert (empty or
    cosmetic-only payload) and dropped quietly, or active (a live
    clue/negative list or a populated group) and dropped loudly, named by its
    `definition.name` when the link carries one. Honoring a specific variant
    rather than dropping it is the opt-in variant-decoder path; each variant
    still warns on the part it can't model (a kropki/XV `negative` list),
    fired from its own decoder instead.

    `has_live_data` is the shared active/inert predicate: this runtime policy
    and `scripts/inspect_link.py`'s `classify_constraint` both
    call it, so the dev tool's report and what the decoder actually drops can
    never disagree."""
    constraints = puzzle_data.get("constraints", [])
    if not isinstance(constraints, list):
        return
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
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


def has_live_data(constraint: dict[Any, Any]) -> bool:
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
    boundary type (a dict narrowed from the untyped payload), as `decode_link`
    does for `puzzle_data`."""
    if constraint.get("type") in _TOGGLE_WIRE_TYPES:
        return True
    for key in _LIVE_LIST_KEYS:
        value = constraint.get(key)
        if isinstance(value, list) and any(value):
            return True
    payload = constraint.get("input")
    if isinstance(payload, dict):
        groups = payload.get("groups")
        if isinstance(groups, list) and any(
            isinstance(group, dict) and group.get("cells") for group in groups
        ):
            return True
    return False


def constraint_name(constraint: dict[Any, Any]) -> str | None:
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
