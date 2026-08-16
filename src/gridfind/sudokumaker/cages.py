"""Cell-group block decoders: killer cages (`type 301`), cosmetic cages
(`type 2001` — killer-shaped but dispatched per its marker classification,
`markers.cosmetic_cage_kind`), and thermometers (`type 300`, the one
ordered-path block, grouped here alongside the cages since it shares their
raw-indices-to-addresses wire shape and no other module in the split claims
it).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from gridfind.puzzle import Constraint, ModifierDirective
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.cells import _addresses
from gridfind.sudokumaker.markers import (
    _COSMETIC_CAGE_TYPE,
    CosmeticCageKind,
    cosmetic_cage_kind,
)

# type 301 is a killer-cage block: `cages: [{cells, value}]`. A
# positive `value` is the killer sum, decoded onto a `group-sum` alongside the
# `cage` (no-repeats) constraint, both over the same cells (ADR-0009) — 0 is
# SudokuMaker's own no-sum cage, decoding to `cage` alone, exactly as `value`
# absent.
_CAGE_TYPE = 301

# type 300 is a thermometer block: `slow: bool,
# thermometers: [[cell indices, ordered, bulb first], …]`. Each path becomes
# its own `thermo` Constraint; `slow` rides through onto every path in the
# block. The strict-vs-non-strict split is the `thermo` layer's concern, not
# the decoder's.
_THERMO_TYPE = 300


def _killer_cage(addresses: list[str], total: int | None) -> list[Constraint]:
    """A killer cage over `addresses`: always a no-repeats `cage`, plus a
    `group-sum` carrying `total` when a total is present (ADR-0009). A zero or
    `None` total is no total — the cage stands alone."""
    decoded = [Constraint("cage", params={"cells": addresses})]
    if total:
        decoded.append(
            Constraint("group-sum", params={"cells": addresses, "sum": total})
        )
    return decoded


def cage_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 301` killer cages as `Constraint`s: each cage's raw `cells`
    indices map row-major to addresses (`_addresses`), so `[18, 19]` on a
    9-board is R3C1/R3C2. Every cage decodes to a no-repeats `cage`; a positive
    `value` additionally decodes a `group-sum` over the same cells (ADR-0009) —
    `0` (SudokuMaker's own no-sum cage) decodes to `cage` alone, exactly as an
    absent `value`. A `disabled` block is skipped entirely; an empty `cages`
    list adds nothing."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, _CAGE_TYPE):
        cages = cast("list[dict[str, Any]]", block.get("cages", []))
        for cage in cages:
            addresses = _addresses(cage["cells"], size)
            decoded.extend(_killer_cage(addresses, cage.get("value", 0)))
    return decoded


def _cosmetic_cage_killer_sum(cage: dict[Any, Any]) -> int | None:
    """The killer sum a `type 2001` cosmetic cage graduates to (ADR-0008),
    or `None` when its `value` label is non-numeric/empty and the cage carries
    no sum. `None` governs only the `group-sum`: a sumless cosmetic cage still
    emits its no-repeats `cage`, so this is not a liveness gate — every
    non-disabled cage with cells is a rule."""
    value = cage.get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class _CosmeticCageDecode:
    """The `Constraint`s and `ModifierDirective`s one `type 2001` block
    decodes to — a `Sum`/`Killer`-labelled block contributes killer-cage
    constraints, a `Doubler`-marked block contributes modifier directives
    instead, an unnamed or unrecognized-named block contributes nothing
    (ADR-0012's warn-drop), and `concat` folds a link's worth of blocks into
    the two lists `decode_link` reads."""

    constraints: tuple[Constraint, ...] = ()
    modifier_directives: tuple[ModifierDirective, ...] = ()

    @classmethod
    def concat(cls, decodes: Iterable[_CosmeticCageDecode]) -> _CosmeticCageDecode:
        decodes = list(decodes)
        return cls(
            constraints=tuple(c for d in decodes for c in d.constraints),
            modifier_directives=tuple(
                m for d in decodes for m in d.modifier_directives
            ),
        )


def _warn_dropped_cosmetic_cage(block: dict[str, Any], kind: CosmeticCageKind) -> None:
    """Warn to stderr that a live `type 2001` block carries no rule: `kind` is
    `"unnamed"` (absent/blank name) or `"unrecognized"` (a name the registry
    doesn't answer for) — either way only a recognized name selects a rule
    (ADR-0012), so the verdict is computed without this block. Named after
    the case so the message tells the setter which one they hit."""
    if kind == "unnamed":
        msg = "warning: ignoring unnamed cosmetic cage — verdict computed without it"
    else:
        msg = (
            f"warning: ignoring unrecognized named cage {block.get('name')!r} "
            "— verdict computed without it"
        )
    print(msg, file=sys.stderr)


def cosmetic_cage_constraints(
    buckets: ConstraintBuckets, size: int
) -> _CosmeticCageDecode:
    """The `type 2001` cosmetic-cage blocks decoded per their top-level `name`
    (`cosmetic_cage_kind`, ADR-0012): a `Sum`/`Killer`-labelled block
    graduates to killer-cage `Constraint`s (ADR-0008) — cells and value
    nest under `cages`, the same wire shape as a `type 301` block, each cage's
    raw `cells` indices mapping row-major to addresses, every non-disabled
    cage emitting a no-repeats `cage` plus a `group-sum` when its numeric
    non-zero string `value` carries a total (ADR-0009). A `Doubler`-marked
    block instead emits one `ModifierDirective(is_modifier=True)` per cell it
    contains and **no** `cage`/`group-sum` — the block's `cages` still supply
    the cell list, just not a killer rule. An `S-cell`/`Schrödinger`-marked
    block emits nothing here: its cells become S-cell working-state directives
    in the per-cell decode pass (`scell_marker_values` gathers them, cage
    `value` and all), not a cage rule. An **unnamed** block, or one whose name
    gridfind does not recognize, carries no rule at all — only a recognized
    name selects one. A non-empty one is dropped with a loud stderr warning
    naming the block or its unrecognized name; an empty one adds nothing and
    warns nothing, the same as any other empty block. A `disabled` block is
    skipped entirely."""
    decoded: list[_CosmeticCageDecode] = []
    for block in enabled_blocks(buckets, _COSMETIC_CAGE_TYPE):
        kind = cosmetic_cage_kind(block.get("name"))
        cages = cast("list[dict[str, Any]]", block.get("cages", []))
        if kind in ("unnamed", "unrecognized"):
            if cages:
                _warn_dropped_cosmetic_cage(block, kind)
            continue
        if kind == "s-cell":
            continue
        if kind == "doubler":
            modifiers = tuple(
                ModifierDirective(address, is_modifier=True)
                for cage in cages
                for address in _addresses(cage["cells"], size)
            )
            decoded.append(_CosmeticCageDecode(modifier_directives=modifiers))
            continue
        constraints: list[Constraint] = []
        for cage in cages:
            addresses = _addresses(cage["cells"], size)
            constraints.extend(_killer_cage(addresses, _cosmetic_cage_killer_sum(cage)))
        decoded.append(_CosmeticCageDecode(constraints=tuple(constraints)))
    return _CosmeticCageDecode.concat(decoded)


def thermo_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 300` thermometers as `thermo` `Constraint`s: each path's raw indices
    map row-major to addresses, order
    preserved (bulb first) — order is the whole point of a line, unlike
    `cage`'s unordered `cells`. `slow` rides through verbatim onto every path
    in the block. A `disabled` block is skipped entirely; an empty
    `thermometers` list adds nothing. The cosmetic `style` object is
    ignored."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, _THERMO_TYPE):
        slow = bool(block.get("slow", False))
        paths = cast("list[list[int]]", block.get("thermometers", []))
        for path in paths:
            addresses = _addresses(path, size)
            params: dict[str, object] = {"path": addresses, "slow": slow}
            decoded.append(Constraint("thermo", params=params))
    return decoded
