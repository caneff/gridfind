"""Per-cell decode: one wire cell's working-state directives
(`decode_cell`/`CellDecode`), the S-cell marker-value parse
(`_scell_directive_from_value`/`_parse_scell_value`), and the one wire-write
seam for a witness cell (`write_cell`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from gridfind.puzzle import Candidate, Given, Placement
from gridfind.s_directives import (
    BareSCell,
    HalfSCell,
    SCellMarkRestriction,
    SCellPin,
    SDirective,
    SingletonPin,
)

# An S-cell marker cage's `value` selects the directive by parsed digit-count
# (ADR-0014): two digits pin the pair, one is the looser half directive.
_SCELL_PIN_DIGITS = 2

# A single-digit domain's largest representable digit — a cage `value` of two
# bare digit characters (no comma) is the pair shorthand only when every
# domain digit fits in one character (CONTEXT.md, "Cage-value pair source"); a
# wider domain (e.g. 16x16's 10..16) needs the unambiguous comma form for a
# pair, so a bare two-character value there reads as one two-digit half-cell
# digit instead.
_MAX_SINGLE_DIGIT = 9


@dataclass(frozen=True)
class CellDecode:
    """The working-state directives one cell decodes to — the return of
    `decode_cell`, which hands a cell's directives back as one value. A cell
    touches only a few of the four channels: a plain
    `given`, a `placement`, a `candidate` set, or a Schrödinger `s_directive`
    (optionally with a stray-marks candidate beside it). All empty is a cell
    that carries nothing gridfind represents. (A doubler's `modifier_directive`
    rides on its marker cage, not the cell, so it is decoded there, not here.)

    The four tuples mirror the directive channels the decoder fills, so
    `concat` folds a board's worth of per-cell decodes into the lists
    `Puzzle`/`WorkingState` read."""

    givens: tuple[Given, ...] = ()
    places: tuple[Placement, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    s_directives: tuple[SDirective, ...] = ()

    @classmethod
    def concat(cls, decodes: Iterable[CellDecode]) -> CellDecode:
        """One `CellDecode` merging every cell's, each channel concatenated in
        cell order — the board-level directive set `link_to_puzzle` reads."""
        decodes = list(decodes)
        return cls(
            givens=tuple(d for c in decodes for d in c.givens),
            places=tuple(p for c in decodes for p in c.places),
            candidates=tuple(x for c in decodes for x in c.candidates),
            s_directives=tuple(s for c in decodes for s in c.s_directives),
        )


def write_cell(cell: dict[str, Any], content: tuple[int, ...]) -> None:
    """Write a witness cell's content onto the SudokuMaker wire — the one
    wire-write seam, singleton and S-cell through one door, so a caller holding
    a witness never touches the cell's field shape. A length-1 content sets
    `value` alone, leaving `cell`'s own `given` flag untouched: a cell the
    source document already marked given stays a given (the setter's digit),
    while any other cell reads back as a placement (a rule-solved digit) —
    the setter's givens and the rules' placements must stay tellable apart on
    the solution pane (#725). A length-2 content `(a, b)` is a Schrödinger
    S-cell, written via `_write_s_cell` as its two center marks. gridfind
    reads S-cells and doublers from named marker cages, never cell colors, so
    the fill writes no color bits — a declared cell's marker cage rides
    through untouched and marks it."""
    if len(content) == 1:
        cell["value"] = content[0]
    else:
        a, b = content
        _write_s_cell(cell, a, b)


def _write_s_cell(cell: dict[str, Any], a: int, b: int) -> None:
    """Write an S-cell's two-digit pair into `cell` as the `candidates` bitmask
    (its two center marks) — SudokuMaker's cosmetic display of the pair. The
    decode-time pair rides the marker cage's own `value`, not these marks."""
    cell["candidates"] = (1 << a) | (1 << b)


def decode_cell(
    cell: dict[str, Any],
    address: str,
    domain: range,
    *,
    is_schrodinger: bool = False,
    is_scell_marker: bool = False,
    scell_value: object = None,
) -> CellDecode:
    """One cell's working-state directives — the single home for per-cell
    decode, dispatched by the cell's marker membership. A cell in an `S-cell`
    marker cage (`is_scell_marker`) is a declared S-cell: its marker cage's own
    `value` picks the directive (`_scell_directive_from_value`, ADR-0014). A
    settled value on the cell itself is the is-S-vs-settled contradiction: it
    decodes alongside the marker's own directive as a singleton pin, the two
    left to collide at solve time rather than refused here (ADR-0014).
    Every other cell's settled value is a plain `given`/`placement` on a
    non-Schrödinger board, or — once a Schrödinger layer exists — a singleton
    pin (`is_s == 0`); the `given`/`placement` wire distinction does not affect
    the S-cell reading. Doubler-ness rides on the marker cage,
    not the cell, so a marked doubler cell still decodes its digit here
    unchanged. A cell that carries nothing gridfind represents — a cosmetic
    color, a corner mark, `{}` — decodes to an empty `CellDecode`."""
    if is_scell_marker:
        directive = _scell_directive_from_value(address, scell_value, domain)
        directives: tuple[SDirective, ...] = (directive,)
        if "candidates" in cell:
            marks = _read_candidates_bitmask(cell["candidates"], domain)
            if marks:
                directives += (SCellMarkRestriction(address, marks),)
        if "value" in cell:
            directives += (SingletonPin(address, cell["value"]),)
        return CellDecode(s_directives=directives)
    if "value" in cell:
        if is_schrodinger:
            return CellDecode(s_directives=(SingletonPin(address, cell["value"]),))
        if cell.get("given"):
            return CellDecode(givens=(Given(address, cell["value"]),))
        return CellDecode(places=(Placement(address, cell["value"]),))
    if "candidates" in cell:
        digits = _read_candidates_bitmask(cell["candidates"], domain)
        return CellDecode(candidates=(Candidate(address, digits),))
    return CellDecode()


def _read_candidates_bitmask(bitmask: int, domain: range) -> frozenset[int]:
    """A wire cell's `candidates` bitmask read as the set of domain digits it
    marks — the one home for this read, called by both `decode_cell` branches
    that carry a `candidates` field (the S-cell stray-marks restriction and the
    plain pencil-mark candidate set)."""
    return frozenset(d for d in domain if bitmask & (1 << d))


def _scell_directive_from_value(
    address: str, value: object, domain: range
) -> SDirective:
    """A declared S-cell's directive chosen by its marker cage's own `value`
    digit-count (ADR-0012): two parsed digits pin the pair, one is a
    half S-cell, zero — absent, empty, or unparseable — is a bare S-cell."""
    digits = _parse_scell_value(value, domain)
    if len(digits) == _SCELL_PIN_DIGITS:
        return SCellPin(address, frozenset(digits))
    if len(digits) == 1:
        return HalfSCell(address, digits[0])
    return BareSCell(address)


def _parse_scell_value(value: object, domain: range) -> tuple[int, ...]:
    """An S-cell marker cage's raw `value` parsed to its digits, never
    raising: a comma-separated `"a,b"` splits into its pair; a bare two-digit
    string is the pair shorthand `"ab"` when every domain digit is
    single-character (else it is one two-digit value); anything else parses as
    one digit. A value that is absent, empty, or doesn't cleanly fit one of
    those shapes parses to `()` — a bare S-cell, never a crash. A cleanly
    parsed digit outside `domain` is kept, not dropped: it rides into the
    directive for the verdict-time domain guard to refuse (CONTEXT.md,
    "malformed")."""
    if not isinstance(value, str) or not value.strip():
        return ()
    text = value.strip()
    if "," in text:
        parts = text.split(",")
        if len(parts) != _SCELL_PIN_DIGITS:
            return ()
        return _parse_digit_pair(parts[0], parts[1])
    if (
        len(text) == _SCELL_PIN_DIGITS
        and text.isdigit()
        and domain.stop - 1 <= _MAX_SINGLE_DIGIT
    ):
        return _parse_digit_pair(text[0], text[1])
    digit = _parse_digit(text)
    return (digit,) if digit is not None else ()


def _parse_digit_pair(first: str, second: str) -> tuple[int, ...]:
    """Both digit strings parsed, kept as the pair only if both parse cleanly —
    the one home for this rule, called by `_parse_scell_value`'s comma and bare
    two-digit shorthand paths alike. Either side failing to parse drops the
    whole pair, never a lone digit."""
    a = _parse_digit(first)
    b = _parse_digit(second)
    return (a, b) if a is not None and b is not None else ()


def _parse_digit(text: str) -> int | None:
    """One digit string parsed to an `int`, or `None` when `text` is not a
    clean integer. An out-of-domain digit is returned as-is, never masked: it
    rides into the S-cell directive so the verdict-time domain guard refuses it
    as malformed, exactly as an out-of-domain given does (CONTEXT.md,
    "malformed"). Only genuine non-numeric text reads as a bare S-cell."""
    try:
        return int(text.strip())
    except ValueError:
        return None
