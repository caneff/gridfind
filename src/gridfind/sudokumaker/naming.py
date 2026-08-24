"""The name -> shape registry (ADR-0012): the one table
gridfind consults when a component's declared name selects a rule. A
`cage-selector` name (`Sum`, `Killer`, `Equality`, `Rellik`/`Anti`) picks a
cage rule — the plain killer sum for `Sum`/`Killer`, `cage` + `equality-cage`
for `Equality`, the anti-cage subset-sum ban for `Rellik`/`Anti` (ADR-0018); a
`cell-marker` name (`Doubler`, `S-cell`/`Schrödinger`) declares a cage's cells
a position marker instead; a `global-flag` name (`Somedoku`) needs no payload
at all — its cells and value, if the carrier even has them, are ignored, and
presence of the name alone selects its rule. The two cell-needing shapes fail
carrier-fitness on a name-bearing carrier that has none — a `type 1000` custom
constraint's `definition.name`, unlike a `type 2001` cosmetic cage's top-level
`name` — (`shape_needs_cells`);
`sudokumaker.registry` reads that to warn-drop a cage-shaped name stranded on
the wrong carrier. A `global-flag` name needs nothing, so it is admitted on
both carriers alike.

`_NAME_REGISTRY` is a static key set except for one **parameterized** name
(ADR-0016): `Constant <N>` carries its own integer, so it cannot live as a
fixed dict key like every other name. `named_component` falls to
`_parsed_constant_component` when a normalized name misses the static table,
parsing the trailing integer off a leading `constant` token; `Nullifier`, the
`k = 0` spelling, stays a static entry since it needs no payload of its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_Shape = Literal["cage-selector", "cell-marker", "global-flag"]

# The one role enum a `type 2001` cosmetic cage's `name` sorts into
# (`classify`): the eight named roles a `_NamedComponent` carries, plus
# `"unnamed"` (absent/blank name) and `"unrecognized"` (a name the registry
# doesn't answer for), which `classify` alone produces — no real component
# ever carries either.
Role = Literal[
    "unnamed",
    "killer",
    "equality",
    "rellik",
    "doubler",
    "s-cell",
    "constant",
    "somedoku",
    "numbered-rooms",
    "unrecognized",
]

# `cage-selector`/`cell-marker` need a cage's cells; `global-flag` needs
# nothing — its name alone is the whole signal, so carrier-fitness admits it
# on a carrier with no cells too (`shape_needs_cells`).
_SHAPE_NEEDS_CELLS: dict[_Shape, bool] = {
    "cage-selector": True,
    "cell-marker": True,
    "global-flag": False,
}


def shape_needs_cells(shape: _Shape) -> bool:
    """Whether `shape`'s payload need includes a cage's cells — the property
    carrier-fitness checks a name-bearing carrier against."""
    return _SHAPE_NEEDS_CELLS[shape]


@dataclass(frozen=True)
class _NamedComponent:
    """A name the registry recognizes: `role` is the specific behavior it
    selects (`classify`'s `"doubler"`/`"s-cell"`/`"constant"`/`"somedoku"`,
    `"killer"` for either killer-cage label, or `"equality"` for the
    equality-cage label), `shape` is the payload need carrier-fitness checks,
    and `value` is the integer a `"constant"` role carries (`k`, read from
    the name itself — `Constant <N>`/`Nullifier`) — `None` for every other
    role, which needs no payload of its own. `role` is typed `Role` for reuse
    across the module, but a real component only ever holds one of the eight
    named values — never `"unnamed"`/`"unrecognized"`, which `classify`
    alone produces."""

    role: Role
    shape: _Shape
    value: int | None = None


# The normalized-name -> component table (case-insensitive, trimmed — see
# `_normalize_component_name`). `Sum`/`Killer` share the `"killer"` role: both
# select the plain killer-cage rule, the name itself discarded once
# recognized. `Equality` is its own cage-selector role, selecting `cage` +
# `equality-cage` instead. `Rellik`/`Anti` share the `"rellik"` role: both
# select the anti-cage subset-sum ban, the cage's numeric value read as the
# forbidden total exactly as a killer cage's value is read as its sum.
# `S-cell`/`Schrödinger`/`Schrodinger` share `"s-cell"`: the umlaut spelling
# and its ASCII fold are the same marker. `Nullifier` is the static `k = 0`
# spelling of `"constant"`; `Constant <N>` at any other `k` is not a static key
# here — see `_parsed_constant_component`. `Somedoku` and `Numbered Rooms` are
# the two `global-flag` names, each its own role: the name alone is admitted on
# a type-1000 carrier that has no cage cells, and the rule it selects is
# decoded elsewhere — `line-count-distinct` for Somedoku (`global_flags`),
# the escape-the-grid `numbered-rooms` clue for Numbered Rooms (`frame`).
_NAME_REGISTRY: dict[str, _NamedComponent] = {
    "sum": _NamedComponent(role="killer", shape="cage-selector"),
    "killer": _NamedComponent(role="killer", shape="cage-selector"),
    "equality": _NamedComponent(role="equality", shape="cage-selector"),
    "rellik": _NamedComponent(role="rellik", shape="cage-selector"),
    "anti": _NamedComponent(role="rellik", shape="cage-selector"),
    "doubler": _NamedComponent(role="doubler", shape="cell-marker"),
    "s-cell": _NamedComponent(role="s-cell", shape="cell-marker"),
    "schrödinger": _NamedComponent(role="s-cell", shape="cell-marker"),
    "schrodinger": _NamedComponent(role="s-cell", shape="cell-marker"),
    "nullifier": _NamedComponent(role="constant", shape="cell-marker", value=0),
    "somedoku": _NamedComponent(role="somedoku", shape="global-flag"),
    "numbered rooms": _NamedComponent(role="numbered-rooms", shape="global-flag"),
}

# `Constant <N>`, case/whitespace-normalized: a leading `constant` token, one
# or more spaces, then the integer `k` — the one shape a parameterized name
# takes (ADR-0016). Anything else (a bare `constant`, non-numeric or
# trailing text after the integer) does not match and stays unrecognized,
# never coerced to `k = 0`.
_CONSTANT_NAME_PATTERN = re.compile(r"^constant\s+(-?\d+)$")


def _parsed_constant_component(normalized: str) -> _NamedComponent | None:
    """`normalized` read as `Constant <N>`, or `None` when it doesn't match —
    `named_component`'s fallback once the static `_NAME_REGISTRY` lookup
    misses."""
    match = _CONSTANT_NAME_PATTERN.match(normalized)
    if match is None:
        return None
    return _NamedComponent(
        role="constant", shape="cell-marker", value=int(match.group(1))
    )


def _normalize_component_name(name: object) -> str | None:
    """`name` trimmed and lowercased, or `None` when it isn't a non-blank
    string — the one normalization both name-bearing carriers' reads share."""
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip().lower()


def named_component(name: object) -> _NamedComponent | None:
    """The registry entry `name` declares, or `None` when absent/blank or
    unrecognized — the shared lookup both carriers' name-extraction steps
    feed (a `type 2001` cosmetic cage's top-level `name`, a `type 1000`
    custom constraint's `definition.name` via `dropped.constraint_name`).
    A static `_NAME_REGISTRY` hit wins; a miss falls to
    `_parsed_constant_component` for the one parameterized name,
    `Constant <N>`."""
    normalized = _normalize_component_name(name)
    if normalized is None:
        return None
    component = _NAME_REGISTRY.get(normalized)
    if component is not None:
        return component
    return _parsed_constant_component(normalized)


def classify(name: object) -> Role:
    """Classify a `type 2001` block's top-level `name` (ADR-0012, extended by
    ADR-0016 and ADR-0018) into one of ten kinds: `"unnamed"`
    (absent/blank — a purely decorative block that carries no rule),
    `"killer"` (a recognized `Sum`/`Killer` label that selects the
    killer-cage rule), `"equality"` (a recognized `Equality` label that
    selects `cage` + `equality-cage`), `"rellik"` (a recognized `Rellik`/`Anti`
    label that selects the anti-cage subset-sum ban, the cage's numeric value
    read as the forbidden total), `"doubler"` (a `Doubler` position marker),
    `"s-cell"` (an `S-cell`/`Schrödinger` position marker), `"constant"` (a
    `Constant <N>`/`Nullifier` position marker whose `k` is read from the name
    itself), `"somedoku"` (the payload-less `Somedoku` global flag — cells and
    value ignored), `"numbered-rooms"` (the `Numbered Rooms` global-flag name,
    whose escape-the-grid clue `frame` decodes from the block's own `input`,
    never a cage), or `"unrecognized"` (a name `link_to_puzzle` cannot answer
    for — a bare `Constant` with no parseable integer lands here too, never
    silently `k = 0`). `"unnamed"` and `"unrecognized"` share the same fate
    downstream — a loud stderr warn-drop, never a rule (ADR-0012) — but stay
    distinct kinds here since the warning they produce names the block
    differently. Matching is case-insensitive and trimmed, via
    `named_component`.

    This is the one home the named-cosmetic-cage reads route through — the
    cage decoder, the S-cell presence and membership channels, marker
    colorizing, and dev tools that recognize a marker block without decoding
    the whole link all switch on this kind."""
    component = named_component(name)
    if component is None:
        return "unrecognized" if isinstance(name, str) and name.strip() else "unnamed"
    return component.role


def aliases_by_role() -> dict[str, frozenset[str]]:
    """Every normalized `_NAME_REGISTRY` name, grouped by the specific role it
    resolves to (`"killer"`, `"doubler"`, `"s-cell"`, `"constant"`) rather than
    by shape —
    the presentation grouping `setter_guide` renders as one canonical label
    plus its "other accepted names" per role (ADR-0013)."""
    groups: dict[str, set[str]] = {}
    for name, component in _NAME_REGISTRY.items():
        groups.setdefault(component.role, set()).add(name)
    return {role: frozenset(names) for role, names in groups.items()}
