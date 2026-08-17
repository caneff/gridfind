"""The name -> shape registry (ADR-0012): the one table
gridfind consults when a component's declared name selects a rule. A
`cage-selector` name (`Sum`, `Killer`, `Rellik`/`Anti`) picks a cage rule —
`Sum`/`Killer` the killer-cage rule, `Rellik`/`Anti` the anti-cage subset-sum
ban (spec #427); a `cell-marker` name (`Doubler`, `S-cell`/`Schrödinger`)
declares a cage's cells a position marker instead; a `global-flag` name
(`Somedoku`) needs no payload at all — its cells and value, if the carrier
even has them, are ignored, and presence of the name alone selects its rule.
The two cell-needing shapes fail carrier-fitness on a name-bearing carrier
that has none — a `type 1000` custom constraint's `definition.name`, unlike a
`type 2001` cosmetic cage's top-level `name` — (`shape_needs_cells`);
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
    selects (`cosmetic_cage_kind`'s `"doubler"`/`"s-cell"`/`"constant"`/
    `"somedoku"`, or `"killer"` for either cage-selector label), `shape` is
    the payload need carrier-fitness checks, and `value` is the integer a
    `"constant"` role carries (`k`, read from the name itself — `Constant
    <N>`/`Nullifier`) — `None` for every other role, which needs no payload
    of its own."""

    role: Literal["killer", "doubler", "s-cell", "constant", "somedoku", "rellik"]
    shape: _Shape
    value: int | None = None


# The normalized-name -> component table (case-insensitive, trimmed — see
# `_normalize_component_name`). `Sum`/`Killer` share the `"killer"` role: both
# select the plain killer-cage rule, the name itself discarded once
# recognized. `Rellik`/`Anti` share the `"rellik"` role: both select the
# anti-cage subset-sum ban, the cage's numeric value read as the forbidden
# total exactly as a killer cage's value is read as its sum. `S-cell`/
# `Schrödinger`/`Schrodinger` share `"s-cell"`: the umlaut spelling and its
# ASCII fold are the same marker. `Nullifier` is the static `k = 0` spelling
# of `"constant"`; `Constant <N>` at any other `k` is not a static key here —
# see `_parsed_constant_component`. `Somedoku` is the sole `global-flag`
# name: its own role, needing no payload.
_NAME_REGISTRY: dict[str, _NamedComponent] = {
    "sum": _NamedComponent(role="killer", shape="cage-selector"),
    "killer": _NamedComponent(role="killer", shape="cage-selector"),
    "rellik": _NamedComponent(role="rellik", shape="cage-selector"),
    "anti": _NamedComponent(role="rellik", shape="cage-selector"),
    "doubler": _NamedComponent(role="doubler", shape="cell-marker"),
    "s-cell": _NamedComponent(role="s-cell", shape="cell-marker"),
    "schrödinger": _NamedComponent(role="s-cell", shape="cell-marker"),
    "schrodinger": _NamedComponent(role="s-cell", shape="cell-marker"),
    "nullifier": _NamedComponent(role="constant", shape="cell-marker", value=0),
    "somedoku": _NamedComponent(role="somedoku", shape="global-flag"),
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
    custom constraint's `definition.name` via `registry.constraint_name`).
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
