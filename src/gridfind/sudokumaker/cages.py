"""Cell-group block decoders: killer cages (`type 301`), cosmetic cages
(`type 2001` — killer-shaped but dispatched per its marker classification,
`naming.classify`), and thermometers (`type 300`, the one
ordered-path block, grouped here alongside the cages since it shares their
raw-indices-to-addresses wire shape and no other module in the split claims
it).
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import Any, Literal, cast

from gridfind.engine import MalformedPuzzleError
from gridfind.puzzle import Constraint, ModifierDirective
from gridfind.sudokumaker.addresses import addresses
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.naming import Role, classify, named_component
from gridfind.sudokumaker.wire_types import CAGE_TYPE, COSMETIC_CAGE_TYPE, THERMO_TYPE

_ModifierKind = Literal["doubler", "constant"]


def _cage_with_optional_total(
    addresses: list[str], total: int | None, total_constraint_type: str
) -> list[Constraint]:
    """A cage over `addresses`: always a no-repeats `cage`, plus a
    `total_constraint_type` constraint carrying `total` when a total is
    present (ADR-0009) — `"group-sum"` for a killer cage's target sum,
    `"rellik-cage"` for a rellik cage's forbidden total. A zero or `None`
    total is no total — the cage stands alone."""
    decoded = [Constraint("cage", params={"cells": addresses})]
    if total:
        decoded.append(
            Constraint(total_constraint_type, params={"cells": addresses, "sum": total})
        )
    return decoded


def _equality_cages(cages: list[dict[str, Any]], size: int) -> list[Constraint]:
    """Walk `cages`' raw `cells` indices to addresses and decode each to an
    equality cage: a no-repeats `cage` plus `equality-cage` over the same
    cells (ADR-0009's composition shape) — no numeric argument, unlike a
    killer cage's `group-sum`, so a cage's `value` label is never read here.
    An odd cell count is not refused at this seam: `equality-cage` itself
    raises `MalformedPuzzleError` once the puzzle reaches emit."""
    decoded: list[Constraint] = []
    for cage in cages:
        cage_addresses = addresses(cage["cells"], size)
        decoded.append(Constraint("cage", params={"cells": cage_addresses}))
        decoded.append(Constraint("equality-cage", params={"cells": cage_addresses}))
    return decoded


def _cages_with_optional_total(
    cages: list[dict[str, Any]],
    size: int,
    sum_of: Callable[[dict[str, Any]], int | None],
    total_constraint_type: str,
) -> list[Constraint]:
    """Walk `cages`' raw `cells` indices to addresses (row-major, `addresses`)
    and decode each to a cage (`_cage_with_optional_total`) — the walk a
    `type 301` block and a `Sum`/`Killer`/`Rellik`/`Anti`-named `type 2001`
    block share, differing only in where a cage's total comes from: `sum_of`
    reads it straight off the wire `value` int for a killer cage, or parses
    the cosmetic cage's string `value` label for a cosmetic one, and in which
    constraint type (`total_constraint_type`) the total attaches to."""
    decoded: list[Constraint] = []
    for cage in cages:
        cage_addresses = addresses(cage["cells"], size)
        decoded.extend(
            _cage_with_optional_total(
                cage_addresses, sum_of(cage), total_constraint_type
            )
        )
    return decoded


def cage_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 301` killer cages as `Constraint`s: each cage's raw `cells`
    indices map row-major to addresses (`addresses`), so `[18, 19]` on a
    9-board is R3C1/R3C2. Every cage decodes to a no-repeats `cage`; a positive
    `value` additionally decodes a `group-sum` over the same cells (ADR-0009) —
    `0` (SudokuMaker's own no-sum cage) decodes to `cage` alone, exactly as an
    absent `value`. A `disabled` block is skipped entirely; an empty `cages`
    list adds nothing."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, CAGE_TYPE):
        cages = cast("list[dict[str, Any]]", block.get("cages", []))
        decoded.extend(
            _cages_with_optional_total(
                cages, size, lambda cage: cage.get("value", 0), "group-sum"
            )
        )
    return decoded


def _cosmetic_cage_numeric_value(cage: dict[str, Any]) -> int | None:
    """The integer a `type 2001` cosmetic cage's `value` label carries, or
    `None` when it's non-numeric/empty — the killer sum a `Sum`/`Killer`
    cage graduates to (ADR-0008), or the forbidden total a `Rellik`/`Anti`
    cage graduates to (ADR-0018), read by the same string-to-int parse
    either way. `None` governs only the second constraint (`group-sum` or
    `rellik-cage`): a valueless cosmetic cage still emits its no-repeats
    `cage`, so this is not a liveness gate — every non-disabled cage with
    cells is a rule."""
    value = cage.get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class _CosmeticCageDecode:
    """Everything one `type 2001` block contributes, gathered in the single
    walk `cosmetic_cage_constraints` makes over the link's marker cages — a
    `Sum`/`Killer`-labelled block contributes killer-cage constraints, a
    `Doubler`/`Constant`/`Nullifier`-marked block contributes modifier
    directives instead, an `S-cell`/`Schrödinger`-marked block contributes
    its pinned cell->value mapping and marks its own presence
    (`scell_values`/`has_scell_block`, ADR-0014), a `Somedoku`-marked block
    marks its own presence (`has_somedoku_block`, ADR-0017), and an unnamed
    or unrecognized-named block contributes nothing (ADR-0012's warn-drop).
    `concat` folds a link's worth of blocks into the merged result
    `link_to_puzzle` reads. `modifier_constraint` is not per-block:
    `cosmetic_cage_constraints` resolves it once, across every
    modifier-marked block in the link, and stamps it onto the final merged
    result (`Constraint("doubler")` or `Constraint("constant", {value: k})`,
    or `None` when the link declares no modifier at all — ADR-0016)."""

    constraints: tuple[Constraint, ...] = ()
    modifier_directives: tuple[ModifierDirective, ...] = ()
    modifier_constraint: Constraint | None = None
    scell_values: dict[str, object] = field(default_factory=dict)
    has_scell_block: bool = False
    has_somedoku_block: bool = False

    @classmethod
    def concat(cls, decodes: Iterable[_CosmeticCageDecode]) -> _CosmeticCageDecode:
        decodes = list(decodes)
        scell_values: dict[str, object] = {}
        for decode in decodes:
            scell_values.update(decode.scell_values)
        return cls(
            constraints=tuple(c for d in decodes for c in d.constraints),
            modifier_directives=tuple(
                m for d in decodes for m in d.modifier_directives
            ),
            scell_values=scell_values,
            has_scell_block=any(d.has_scell_block for d in decodes),
            has_somedoku_block=any(d.has_somedoku_block for d in decodes),
        )


def _warn_dropped_cosmetic_cage(block: dict[str, Any], kind: Role) -> None:
    """Warn to stderr that a live `type 2001` block carries no rule: `kind` is
    `"unnamed"` (absent/blank name) or `"unrecognized"` (a name the registry
    doesn't answer for — a bare `Constant` with no parseable integer lands
    here too, ADR-0016) — either way only a recognized name selects a rule
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


def _refuse_marker_cage_value_field(
    cages: Iterable[dict[str, Any]], kind: _ModifierKind
) -> None:
    """Refuse a `Doubler`/`Constant`/`Nullifier` marker cage that carries a
    non-blank per-cage `value` — a modifier's `k` is a puzzle-wide fact the
    cage *name* declares, not a per-cage field two cages could disagree on
    (ADR-0016 decision 3). A blank/absent `value` is not a declaration and
    passes through unchanged, matching how a killer cage's own blank `value`
    reads as no total."""
    for cage in cages:
        value = cage.get("value")
        if isinstance(value, str) and value.strip():
            msg = (
                f"a {kind} marker cage may not carry a per-cage value "
                f"({value!r}) — a modifier's k is declared by the cage name, "
                "puzzle-wide, not a per-cage field"
            )
            raise MalformedPuzzleError(msg)


def _resolve_modifier_constraint(
    declarations: list[tuple[_ModifierKind, int | None]],
) -> Constraint | None:
    """The single modifier `Constraint` every modifier-marked block in the
    link agrees on, or `None` when the link declares none (ADR-0016 decision
    4: one modifier type per puzzle). `declarations` holds one `(kind, k)`
    entry per block that actually marked cells — an empty marker block
    contributes nothing, the same as an empty `Doubler` block always has.
    Refuses a link mixing `doubler` and `constant` declarations, and refuses
    two `constant` declarations naming different `k` — either way, a link
    stating conflicting facts about a puzzle-wide value is malformed rather
    than silently resolved by picking one."""
    if not declarations:
        return None
    kinds = {kind for kind, _ in declarations}
    if len(kinds) > 1:
        msg = (
            "a puzzle may declare one modifier type, not both Doubler and "
            "Constant/Nullifier marker cages"
        )
        raise MalformedPuzzleError(msg)
    kind = next(iter(kinds))
    if kind == "doubler":
        return Constraint("doubler")
    values = {value for _, value in declarations if value is not None}
    if len(values) > 1:
        msg = f"Constant marker cages disagree on k: {sorted(values)}"
        raise MalformedPuzzleError(msg)
    return Constraint("constant", params={"value": next(iter(values))})


def _decode_cosmetic_block(
    kind: Role,
    block: dict[str, Any],
    cages: list[dict[str, Any]],
    size: int,
) -> tuple[_CosmeticCageDecode, tuple[_ModifierKind, int | None] | None]:
    """One `type 2001` block's contribution, decoded per `kind`
    (`naming.classify`, ADR-0012, extended by ADR-0016 and ADR-0018), with
    no outer state: the block in, `(decode, declaration)` out. A
    `Sum`/`Killer`-labelled block graduates to killer-cage `Constraint`s
    (ADR-0008) — cells and value nest under `cages`, the same wire shape as a
    `type 301` block, each cage's raw `cells` indices mapping row-major to
    addresses, every non-disabled cage emitting a no-repeats `cage` plus a
    `group-sum` when its numeric non-zero string `value` carries a total
    (ADR-0009). An `Equality`-labelled block graduates the same cells to `cage`
    + `equality-cage` instead (`_equality_cages`) — no numeric argument, so its
    `value` is never read; an odd cell count is not refused here, only once the
    puzzle reaches emit. A `Rellik`/`Anti`-labelled block graduates the same
    walk to a `cage` plus a `rellik-cage` instead, its `value` read as the
    forbidden total rather than a target sum — the `cage` (no-repeats) stands
    alone when the value is blank/non-numeric/zero, exactly as a sumless killer
    cage does. A `Doubler`/`Constant <N>`/`Nullifier`-marked block instead emits one
    `ModifierDirective(is_modifier=True)` per cell it contains and **no**
    `cage`/`group-sum` — the block's `cages` still supply the cell list, just
    not a killer rule; the modifier's own `k` is read from the name
    (`Nullifier` = `Constant 0`), never a per-cage `value` field, which is
    refused outright when present (`_refuse_marker_cage_value_field`). When the
    block actually marks cells, its `(kind, k)` is returned as the declaration
    — the caller resolves the single puzzle-wide modifier `Constraint` across
    every block's declaration (`_resolve_modifier_constraint`); every other
    kind returns `None` for the declaration. An `S-cell`/`Schrödinger`-marked
    block emits no cage/modifier `Constraint`: instead it contributes its own
    presence (`has_scell_block`) and, for each cell it contains, that cell's
    marker cage's raw `value` (`scell_values`) — the two S-cell signals
    `link_to_puzzle` reads for the per-cell decode pass (ADR-0014). A
    `Somedoku`-marked block likewise emits no `Constraint` — it carries no
    cell-level reading at all, cells and value alike ignored — contributing
    only its own presence (`has_somedoku_block`), which `link_to_puzzle` folds
    with the `type 1000` carrier (`global_flags.has_somedoku_component`) to
    decide whether the `line-count-distinct` constraint stands up puzzle-wide.
    An **unnamed** block, or one whose name gridfind does not recognize (a bare
    `Constant` with no parseable integer included), carries no rule at all —
    only a recognized name selects one. A non-empty one is dropped with a loud
    stderr warning naming the block or its unrecognized name; an empty one
    adds nothing and warns nothing, the same as any other empty block."""
    if kind in ("unnamed", "unrecognized"):
        if cages:
            _warn_dropped_cosmetic_cage(block, kind)
        return _CosmeticCageDecode(), None
    if kind == "s-cell":
        scell_values = {
            cell_address: cage.get("value")
            for cage in cages
            for cell_address in addresses(cage["cells"], size)
        }
        return (
            _CosmeticCageDecode(scell_values=scell_values, has_scell_block=True),
            None,
        )
    if kind == "somedoku":
        return _CosmeticCageDecode(has_somedoku_block=True), None
    if kind in ("doubler", "constant"):
        _refuse_marker_cage_value_field(cages, kind)
        modifiers = tuple(
            ModifierDirective(format_address, is_modifier=True)
            for cage in cages
            for format_address in addresses(cage["cells"], size)
        )
        declaration = None
        if modifiers:
            component = named_component(block.get("name"))
            value = component.value if component is not None else None
            declaration = (kind, value)
        return _CosmeticCageDecode(modifier_directives=modifiers), declaration
    if kind == "equality":
        return _CosmeticCageDecode(
            constraints=tuple(_equality_cages(cages, size))
        ), None
    if kind == "rellik":
        constraints = _cages_with_optional_total(
            cages, size, _cosmetic_cage_numeric_value, "rellik-cage"
        )
        return _CosmeticCageDecode(constraints=tuple(constraints)), None
    constraints = _cages_with_optional_total(
        cages, size, _cosmetic_cage_numeric_value, "group-sum"
    )
    return _CosmeticCageDecode(constraints=tuple(constraints)), None


def cosmetic_cage_constraints(
    buckets: ConstraintBuckets, size: int
) -> _CosmeticCageDecode:
    """The `type 2001` cosmetic-cage blocks, each decoded independently by
    `_decode_cosmetic_block` and gathered here: every block's decode is
    appended to the merged result (`_CosmeticCageDecode.concat`), and a
    modifier-marked block's declaration — when it made one — is appended to
    the list `_resolve_modifier_constraint` reduces to the single
    `doubler`/`constant` `Constraint` the whole link agrees on (`None` when
    the link declares no modifier at all, ADR-0016); a link mixing modifier
    kinds or naming a `Constant` block two different `k`s is refused with
    `MalformedPuzzleError`. A `disabled` block is skipped entirely.

    This is the one pass `link_to_puzzle` makes over the link's `type 2001`
    blocks — cage/modifier constraints, S-cell presence and pinning, and the
    Somedoku cosmetic-cage carrier all fall out of the same per-block walk."""
    decoded: list[_CosmeticCageDecode] = []
    modifier_declarations: list[tuple[_ModifierKind, int | None]] = []
    for block in enabled_blocks(buckets, COSMETIC_CAGE_TYPE):
        kind = classify(block.get("name"))
        cages = cast("list[dict[str, Any]]", block.get("cages", []))
        decode, declaration = _decode_cosmetic_block(kind, block, cages, size)
        decoded.append(decode)
        if declaration is not None:
            modifier_declarations.append(declaration)
    modifier_constraint = _resolve_modifier_constraint(modifier_declarations)
    return replace(
        _CosmeticCageDecode.concat(decoded), modifier_constraint=modifier_constraint
    )


def thermo_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 300` thermometers as `thermo` `Constraint`s: each path's raw indices
    map row-major to addresses, order
    preserved (bulb first) — order is the whole point of a line, unlike
    `cage`'s unordered `cells`. `slow` rides through verbatim onto every path
    in the block. A `disabled` block is skipped entirely; an empty
    `thermometers` list adds nothing. The cosmetic `style` object is
    ignored."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, THERMO_TYPE):
        slow = bool(block.get("slow", False))
        paths = cast("list[list[int]]", block.get("thermometers", []))
        for path in paths:
            path_addresses = addresses(path, size)
            params: dict[str, object] = {"path": path_addresses, "slow": slow}
            decoded.append(Constraint("thermo", params=params))
    return decoded
