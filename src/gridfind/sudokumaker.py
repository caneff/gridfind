"""Decode a SudokuMaker share link into gridfind's `Puzzle` + `WorkingState`.

Its core function, `decode_link`, mirrors `puzzle.py`'s schema-only role: it
strips the `?puzzle=` payload, lz-string-decompresses it, and maps the
`formatVersion 1.5.0` JSON to the model per the confirmed field-by-field map in
`docs/research/sudoku-link-formats.md` §4a/§4b. Size, digit
domain, and regions are read from the link's own fields — `width`/`size` (else
the classic `9`), `minDigit`/`maxDigit` (else `1..N`), and the `type 1`
regions matrix — so any square N decodes; a classic 9x9 link takes
the size/domain fallbacks and carries its boxes as an explicit `type 1`. A link
gridfind can't answer — non-square, a
cell-count/size mismatch, a domain that doesn't span N, an unknown ruleset — is
rejected with `ValueError` rather than mis-decoded into a confident wrong
verdict.

Regions live *only* in a `type 1` block. A boxed puzzle always ships its boxes
as one (the §4a classic fixture carries it), so its absence means the setter
asked for no regions — a Latin square, rows and columns distinct only, no boxes
invented and no size refused for lacking a box convention. A present matrix
decodes bare when it is the board's box tiling, or rides straight onto the
`regions-distinct` constraint's `params["regions"]` verbatim for a jigsaw,
unvalidated — a malformed matrix surfaces as
`MalformedPuzzleError` from `verdict`, never from here.

Every wire type gridfind decodes or otherwise recognizes — givens, regions,
and each opt-in variant decoder (XV, white-kropki, black-kropki, killer-cage,
thermo, cosmetic-cage) — is one row in `DECODER_REGISTRY`: `decode_link`'s
dispatch, the
dropped-constraint warning path, and `has_live_data`'s active/inert check all
read that one table instead of each restating "type N is decoded" by hand.

Declared variants are inferred from named cosmetic cages, never sniffed from a
color or declared out of band. An `S-cell`/`Schrödinger`-named cage relaxes the
`minDigit` guard to read the widened domain, declares its cells S-cells, and
synthesizes the `schrodinger` constraint from marker presence alone (CONTEXT.md
`schrodinger` layer); a `Doubler`-named cage marks its cells modifiers and
stands up the `doubler` constraint the same way. Every link — Schrödinger or
not — ignores the unmodeled constraint types and `disabled` blocks a real link
carries, warning to stderr only when a dropped one carried live data.

Deliberately kept as `ValueError`, not folded into `MalformedPuzzleError`:
every rejection here fires before a `Puzzle` exists at all — it
is this decoder finding a link it does not support, not gridfind finding a
puzzle it cannot answer. A `Puzzle` `decode_link` does produce is never itself
malformed; a `MalformedPuzzleError` from a *decoded* one would still surface
from `verdict`, same as it would for a hand-built `Puzzle`. Conflating the two
would cost a caller the ability to tell "this share link doesn't decode" from
"this puzzle doesn't hold together" — a distinction worth keeping since only
one of them means the *link* is bad.

No engine, no `verdict` call. Schema in, model out.

`encode_link` sits beside `decode_link` as its inverse: a decoded
document back to an openable link. Two later pieces of work both need it,
so it lands once, on its own.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Literal, cast

from lzstring import LZString

from gridfind.layers import ALIAS_REGISTRY
from gridfind.layers.board import cell_address
from gridfind.layers.regions import BOX_SHAPE, region_map_for
from gridfind.puzzle import (
    BareSCell,
    Board,
    Candidate,
    Constraint,
    Given,
    HalfSCell,
    ModifierDirective,
    Placement,
    Puzzle,
    SCellMarkRestriction,
    SCellPin,
    SDirective,
    SingletonPin,
    WorkingState,
)

# The default board a link describes when it states no `size`/`width`:
# SudokuMaker omits those headers only on the classic 9x9 (§4b, ADR-0011).
_CLASSIC_SIZE = 9

# An S-cell marker cage's `value` selects the directive by parsed digit-count
# (spec #349): two digits pin the pair, one is the looser half directive.
_SCELL_PIN_DIGITS = 2

# A single-digit domain's largest representable digit — a cage `value` of two
# bare digit characters (no comma) is the pair shorthand only when every
# domain digit fits in one character (CONTEXT.md, "Cage-value pair source"); a
# wider domain (e.g. 16x16's 10..16) needs the unambiguous comma form for a
# pair, so a bare two-character value there reads as one two-digit half-cell
# digit instead.
_MAX_SINGLE_DIGIT = 9

# type 202 is XV: `clues: [{value, edge}], negative:
# [...]`. `value` selects the existing group-sum alias — 10 is X, 5 is V
# — never a raw `sum`, so a puzzle carrying both an XV clue and
# a literal group-sum on the same cells still hits the alias's own
# fixed-param conflict check in `expand_constraints`. Read off
# `gridfind.layers.ALIAS_REGISTRY` rather than restated here — the
# sum each alias fixes is stated once, in the registry that also builds it.
_XV_TYPE = 202
_XV_ALIASES: dict[int, str] = {
    cast("int", fixed["sum"]): alias
    for alias, (canonical, fixed) in ALIAS_REGISTRY.items()
    if canonical == "group-sum" and "sum" in fixed
}

# type 200 is white-kropki: `clues: [{value, edge}],
# negative: [...]`, the same wire shape as XV. The type number *is* the
# white/black discriminator — 200 is white/difference, 201 black/ratio — so
# `value` is the target difference, honored verbatim onto the existing
# `pair-difference` layer (a labelled non-1 value is never coerced to 1).
_KROPKI_WHITE_TYPE = 200

# type 201 is black-kropki: the same `clues:
# [{value, edge}], negative: [...]` wire shape as white kropki, `value` read
# as the target integer ratio `k` onto the `pair-ratio` layer (a labelled
# non-2 dot is never coerced to 2). A non-integer `value` raises at decode —
# modeling a wrong verdict would be worse than refusing the link.
_KROPKI_BLACK_TYPE = 201

# type 301 is a killer-cage block: `cages: [{cells, value}]`. A
# positive `value` is the killer sum, decoded onto a `group-sum` alongside the
# `cage` (no-repeats) constraint, both over the same cells (spec #240) — 0 is
# SudokuMaker's own no-sum cage, decoding to `cage` alone, exactly as `value`
# absent.
_CAGE_TYPE = 301

# type 2001 is a cosmetic-cage block: `{cages: [{value: str, cells: [...]}]}`,
# the same nested wire shape as a `type 301` killer block — SudokuMaker's
# decoration tool, not the killer-cage tool (ADR-0008). A numeric string
# `value` graduates a cage to a real killer sum, the only channel an
# out-of-range cage sum (a doubler inside a cage) reaches gridfind through,
# since the killer-cage tool refuses to store one.
_COSMETIC_CAGE_TYPE = 2001

# A cosmetic-cage block's top-level `name` (§4c, spec #324): case-insensitive,
# trimmed, these labels mark a real killer cage decorated with a display name
# rather than a position marker — the name is discarded, the cage decodes as
# ordinary. Any name outside the three recognized sets is unrecognized.
_NAMED_KILLER_CAGE_LABELS = frozenset({"sum", "killer"})

# A cosmetic-cage block's top-level `name` (§4c, spec #324) that marks every
# cell it contains as a declared doubler — a position marker, not a killer
# cage.
_DOUBLER_MARKER_LABELS = frozenset({"doubler"})

# A cosmetic-cage block's top-level `name` (§4c, spec #324) that declares every
# cell it contains a Schrödinger S-cell — a position marker, not a killer cage.
# Both the umlaut spelling and its ASCII fold are recognized (a link may carry
# either), matched case-insensitively and trimmed.
_SCELL_MARKER_LABELS = frozenset({"s-cell", "schrödinger", "schrodinger"})

# A low-saturation display palette for named marker cages, cosmetic only —
# written onto the `type 2001` block's own `color` field, a field
# `decode_link` never reads. Index 0 is red: the slot a link's lone marker
# type always takes, and the slot S-cell takes first when a link mixes marker
# types (`_MARKER_KIND_PRIORITY`, near `colorize_marker_cages`).
_MARKER_COLOR_PALETTE: tuple[str, ...] = ("#fd2323ff", "#2372fdff")

# type 300 is a thermometer block: `slow: bool,
# thermometers: [[cell indices, ordered, bulb first], …]`. Each path becomes
# its own `thermo` Constraint; `slow` rides through onto every path in the
# block. The strict-vs-non-strict split is the `thermo` layer's concern, not
# the decoder's.
_THERMO_TYPE = 300


@dataclass(frozen=True)
class _CellDecode:
    """The working-state directives one cell decodes to — the return of
    `_decode_cell`, which hands a cell's directives back as one value. A cell
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
    def concat(cls, decodes: Iterable[_CellDecode]) -> _CellDecode:
        """One `_CellDecode` merging every cell's, each channel concatenated in
        cell order — the board-level directive set `decode_link` reads."""
        decodes = list(decodes)
        return cls(
            givens=tuple(d for c in decodes for d in c.givens),
            places=tuple(p for c in decodes for p in c.places),
            candidates=tuple(x for c in decodes for x in c.candidates),
            s_directives=tuple(s for c in decodes for s in c.s_directives),
        )


def decode_document(link: str) -> dict[str, object]:
    """A SudokuMaker `?puzzle=` link (or a bare payload) decompressed to its
    full `formatVersion 1.5.0` document — `formatVersion` plus its `puzzle`
    block. The exact reverse of `encode_link`, and `decode_link`'s own first
    step: strip the `?puzzle=` prefix, unquote, lz-string-decompress, parse
    the JSON. `decode_link` keeps only the `puzzle` block; a re-encoder needs
    the whole document to preserve every field the app renders."""
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    document: Any = json.loads(raw)
    return document


def decode_link(
    link: str,
    *,
    ignore_unknown_named_cages: bool = False,
) -> tuple[Puzzle, WorkingState]:
    """Map a SudokuMaker `?puzzle=` link (or a bare payload) to a square-N
    `Puzzle` + `WorkingState`, sizing the board and domain from the link
    itself. Raises `ValueError` on a link gridfind can't answer.

    Doublers and S-cells are **inferred from the link's named marker cages**,
    never declared out of band — a `type 2001` cosmetic-cage block whose
    top-level `name` reads as a marker stands up its variant on its own, and a
    single link may carry both a `Doubler` and an `S-cell` block at once.

    A `type 2001` cosmetic-cage block whose top-level `name` names a
    recognized real-cage label (`Sum`/`Killer`, case-insensitive and trimmed)
    decodes as an ordinary killer cage with the name discarded; any other name
    raises `ValueError` unless `ignore_unknown_named_cages` downgrades that
    refusal to strip-and-honor (spec #324).

    A `type 2001` block named `Doubler` (case-insensitive, trimmed) marks every
    cell it contains a declared doubler — one `ModifierDirective` per cell, no
    `cage`/`group-sum` for that block — and stands up the `doubler` constraint.
    The marker is orthogonal to the cell's digit: a doubler holds one digit
    worth twice its value, so a given or placement on a marked cell still lands.

    A `type 2001` block named `S-cell`/`Schrödinger` is the analogous S-cell
    marker: each contained cell is a declared S-cell reading its marker cage's
    own `value` for the pair/half/bare directive (spec #349) — a comma-split
    `"a,b"` or the two-digit scalar shorthand in a single-digit domain pins the
    pair, one digit is a half S-cell, absent/empty/unparseable is a bare
    S-cell. No `cage`/`group-sum` is emitted for that block. A settled value on
    a marked cell (the cell's own `value`, distinct from the cage's) decodes
    alongside the marker's directive rather than being refused — the two
    collide at solve time (spec #348, #346). The marker widens the domain by
    the classic `k = 1` extra digit (`range(minDigit, minDigit + size + 1)`),
    relaxes the classic-only guard, and synthesizes the `schrodinger`
    constraint. Once that layer exists, every cell's settled `given`/bare
    `value` placement — marked or not — decodes to a **singleton pin**
    (`is_s == 0`), not a plain given/placement: the wire's `given` flag does
    not affect the S-cell reading (spec #348)."""
    puzzle_data: Any = decode_document(link)["puzzle"]
    size = _board_size(puzzle_data)
    _warn_on_dropped_constraints(puzzle_data)

    cells = puzzle_data["cells"]
    # A named `S-cell`/`Schrödinger` block splits into two signals. Its
    # *presence* enables the mode — widening the domain and synthesizing the
    # `schrodinger` constraint that gives every cell the `is_s` freedom the
    # solver discovers S-cells with — even when the block names no cells
    # (ADR-0014). Its *membership* pins known S-cells: each named address maps
    # to its marker cage's own `value`, the pair/half/bare source (spec #349)
    # the S-cell branch of the per-cell decode reads.
    scell_values = _scell_marker_values(puzzle_data, size)
    is_schrodinger = _has_scell_marker_block(puzzle_data)
    domain = (
        _schrodinger_domain(puzzle_data, size)
        if is_schrodinger
        else _digit_domain(puzzle_data, size)
    )
    per_cell: list[_CellDecode] = []
    for i, cell in enumerate(cells):
        address = _address(i, size)
        per_cell.append(
            _decode_cell(
                cell,
                address,
                domain,
                is_schrodinger=is_schrodinger,
                is_scell_marker=address in scell_values,
                scell_value=scell_values.get(address),
            )
        )
    decoded = _CellDecode.concat(per_cell)

    # SudokuMaker leaves rows/cols implicit under `type 0`; gridfind makes both
    # explicit — rows/cols always bare, everything else via DECODER_REGISTRY.
    # The cosmetic-cage type alone takes a decode_link-scoped extra argument
    # (the ignore flag) and returns modifier directives alongside its
    # constraints, so it is dispatched by hand rather than through the
    # registry's generic two-argument, constraints-only call.
    constraints = [Constraint("rows-distinct"), Constraint("cols-distinct")]
    cosmetic_cage_decode = _cosmetic_cage_constraints(
        puzzle_data, size, ignore_unknown_named_cages=ignore_unknown_named_cages
    )
    constraints.extend(cosmetic_cage_decode.constraints)
    for kind, decoded_type in DECODER_REGISTRY.items():
        if kind == _COSMETIC_CAGE_TYPE or decoded_type.handler is None:
            continue
        constraints.extend(decoded_type.handler(puzzle_data, size))
    board = Board(size=size, values=domain)
    if is_schrodinger:
        constraints.append(Constraint("schrodinger"))
    if cosmetic_cage_decode.modifier_directives:
        constraints.append(Constraint("doubler"))

    puzzle = Puzzle(board=board, constraints=tuple(constraints), givens=decoded.givens)
    state = WorkingState(
        places=decoded.places,
        candidates=decoded.candidates,
        s_directives=decoded.s_directives,
        modifier_directives=cosmetic_cage_decode.modifier_directives,
    )
    return puzzle, state


def encode_link(document: dict[str, object]) -> str:
    """A decoded SudokuMaker document (the full `json.loads(raw)` object
    `decode_link` reads — `formatVersion` plus its `puzzle` block) mapped back
    to an openable `sudokumaker.app` URL. The exact reverse of `decode_link`'s
    payload step: lz-string-compress the document's JSON to an
    encoded URI component, then prepend the `?puzzle=` prefix `decode_link`
    strips. `document` rides through untouched, so its `size`/`type`-bearing
    fields survive verbatim and the link opens as the same puzzle."""
    payload = LZString.compressToEncodedURIComponent(json.dumps(document))
    return f"https://sudokumaker.app/?puzzle={payload}"


def _board_size(puzzle_data: dict[str, object]) -> int:
    """The board's size `N` read from the link, most specific first (§4b): a
    `width` (with `height`, else derived from the cell count), else a `size`,
    else the classic default `9` — SudokuMaker omits `size`/`width` only when
    the board is the default 9x9, so an absent header means 9, never an
    inference from the cell count (ADR-0011). The shape must be square
    (`rows == cols`) and its cell count must match (`rows * cols == len(cells)`);
    a non-square link, a size/count mismatch, or a sizeless non-81-cell link
    (a real 4x4/6x6 carries its `size`) is refused with its own reason."""
    cells = puzzle_data.get("cells")
    if not isinstance(cells, list):
        msg = "non-classic link: puzzle carries no cells array"
        raise ValueError(msg)
    count = len(cells)
    if "width" in puzzle_data:
        cols = _as_int(puzzle_data["width"], "width")
        height = puzzle_data.get("height")
        rows = _as_int(height, "height") if height is not None else count // (cols or 1)
    elif "size" in puzzle_data:
        rows = cols = _as_int(puzzle_data["size"], "size")
    else:
        rows = cols = _CLASSIC_SIZE
    if rows != cols:
        msg = f"non-square link: {rows}x{cols} is not a square grid"
        raise ValueError(msg)
    if rows * cols != count:
        msg = f"non-classic link: {count} cells do not match size {rows}"
        raise ValueError(msg)
    return rows


def _as_int(value: object, field: str) -> int:
    """A link header field that must be an integer, or a `ValueError` naming it
    (a `bool` is not an `int` here — a `True` width is a malformed link)."""
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"non-classic link: {field} must be an int, got {value!r}"
        raise ValueError(msg)
    return value


def _digit_domain(puzzle_data: dict[str, object], size: int) -> range:
    """The board's digit domain (§4b): `minDigit`..`maxDigit` when the link
    carries them, else the implicit `1..N`. `maxDigit` defaults to a full
    `N`-wide span from `minDigit`, and the span is validated against N
    (`maxDigit - minDigit + 1 == N`) — a domain that doesn't fit the board is
    refused. A classic link omits both, so this is `1..9`, unchanged."""
    min_digit = _as_int(puzzle_data.get("minDigit", 1), "minDigit")
    max_digit = _as_int(puzzle_data.get("maxDigit", min_digit + size - 1), "maxDigit")
    if max_digit - min_digit + 1 != size:
        msg = f"non-classic link: domain {min_digit}..{max_digit} is not {size} digits"
        raise ValueError(msg)
    return range(min_digit, max_digit + 1)


def _schrodinger_domain(puzzle_data: dict[str, object], size: int) -> range:
    """The board's digit domain under the classic Schrödinger reading:
    `minDigit` through `minDigit + N`, an `N + 1`-wide span carrying the
    `k = 1` extra digit the classic Schrödinger rule derives, not reads. When
    the link declares no `minDigit`, the extra digit defaults to `0` prepended
    below the base `1…N`, giving the classic `0…N` (ADR-0014); an explicit
    `minDigit` is honored as-is."""
    min_digit = _as_int(puzzle_data.get("minDigit", 0), "minDigit")
    return range(min_digit, min_digit + size + 1)


def write_cell(cell: dict[str, Any], content: tuple[int, ...]) -> None:
    """Write a witness cell's content onto the SudokuMaker wire — the one
    wire-write seam, singleton and S-cell through one door, so a caller holding
    a witness never touches the cell's field shape. A length-1 content is a
    plain given (`given: True, value: d`). A length-2 content `(a, b)` is a
    Schrödinger S-cell, written via `_write_s_cell` as its two center marks.
    gridfind reads S-cells and doublers from named marker cages, never cell
    colors, so the fill writes no color bits — a declared cell's marker cage
    rides through untouched and marks it."""
    if len(content) == 1:
        cell["given"] = True
        cell["value"] = content[0]
    else:
        a, b = content
        _write_s_cell(cell, a, b)


def _write_s_cell(cell: dict[str, Any], a: int, b: int) -> None:
    """Write an S-cell's two-digit pair into `cell` as the `candidates` bitmask
    (its two center marks) — SudokuMaker's cosmetic display of the pair. The
    decode-time pair rides the marker cage's own `value`, not these marks."""
    cell["candidates"] = (1 << a) | (1 << b)


def _decode_cell(
    cell: dict[str, Any],
    address: str,
    domain: range,
    *,
    is_schrodinger: bool = False,
    is_scell_marker: bool = False,
    scell_value: object = None,
) -> _CellDecode:
    """One cell's working-state directives — the single home for per-cell
    decode, dispatched by the cell's marker membership. A cell in an `S-cell`
    marker cage (`is_scell_marker`) is a declared S-cell: its marker cage's own
    `value` picks the directive (`_scell_directive_from_value`, spec #349). A
    settled value on the cell itself is the is-S-vs-settled contradiction: it
    decodes alongside the marker's own directive as a singleton pin, the two
    left to collide at solve time rather than refused here (spec #348, #346).
    Every other cell's settled value is a plain `given`/`placement` on a
    non-Schrödinger board, or — once a Schrödinger layer exists — a singleton
    pin (`is_s == 0`); the `given`/`placement` wire distinction does not affect
    the S-cell reading. Doubler-ness rides on the marker cage,
    not the cell, so a marked doubler cell still decodes its digit here
    unchanged. A cell that carries nothing gridfind represents — a cosmetic
    color, a corner mark, `{}` — decodes to an empty `_CellDecode`."""
    if is_scell_marker:
        directive = _scell_directive_from_value(address, scell_value, domain)
        directives: tuple[SDirective, ...] = (directive,)
        if "candidates" in cell:
            marks = frozenset(d for d in domain if cell["candidates"] & (1 << d))
            if marks:
                directives += (SCellMarkRestriction(address, marks),)
        if "value" in cell:
            directives += (SingletonPin(address, cell["value"]),)
        return _CellDecode(s_directives=directives)
    if "value" in cell:
        if is_schrodinger:
            return _CellDecode(s_directives=(SingletonPin(address, cell["value"]),))
        if cell.get("given"):
            return _CellDecode(givens=(Given(address, cell["value"]),))
        return _CellDecode(places=(Placement(address, cell["value"]),))
    if "candidates" in cell:
        digits = frozenset(d for d in domain if cell["candidates"] & (1 << d))
        return _CellDecode(candidates=(Candidate(address, digits),))
    return _CellDecode()


def _scell_directive_from_value(
    address: str, value: object, domain: range
) -> SDirective:
    """A declared S-cell's directive chosen by its marker cage's own `value`
    digit-count (spec #349, ADR-0012): two parsed digits pin the pair, one is a
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
        a = _parse_digit(parts[0])
        b = _parse_digit(parts[1])
        return (a, b) if a is not None and b is not None else ()
    if (
        len(text) == _SCELL_PIN_DIGITS
        and text.isdigit()
        and domain.stop - 1 <= _MAX_SINGLE_DIGIT
    ):
        a = _parse_digit(text[0])
        b = _parse_digit(text[1])
        return (a, b) if a is not None and b is not None else ()
    digit = _parse_digit(text)
    return (digit,) if digit is not None else ()


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


def _regions_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `regions-distinct` constraint for an `N`x`N` board, or `[]` when
    the link carries no regions at all — a Latin square. Returns a list, not
    `Constraint | None`, so a `DECODER_REGISTRY` entry's handler shares the
    same shape every other decoded type's handler does.

    The region partition lives *only* in a `type 1` block. A boxed SudokuMaker
    puzzle always ships its boxes as an explicit `type 1` matrix (verified: the
    §4a classic fixture carries one), so its absence means the setter asked for
    no regions — rows and columns distinct only, no boxes invented. A present
    matrix decodes bare when it equals the board's box tiling (the engine
    supplies that partition by convention) or rides onto `params["regions"]`
    verbatim for a jigsaw. A
    `disabled: true` type-1 block is skipped — a real link may
    carry a disabled duplicate alongside the live one. Never validated here — a
    malformed matrix surfaces from `verdict`, not decode."""
    matrix = _regions_matrix(puzzle_data)
    if matrix is None:
        return []
    if size in BOX_SHAPE and matrix == _classic_regions_for(size):
        return [Constraint("regions-distinct")]
    return [Constraint("regions-distinct", params={"regions": matrix})]


def _regions_matrix(puzzle_data: dict[str, object]) -> object | None:
    """The enabled `type 1` regions matrix from the link, or `None` when the
    link carries no live jigsaw block."""
    for block in _enabled_blocks(puzzle_data, 1):
        return block.get("regions")
    return None


def _classic_regions_for(size: int) -> list[int]:
    """The standard box partition of an `N`x`N` board as SudokuMaker's flat,
    row-major region-id array — the matrix a `type 1` block equal to it is
    just the classic tiling of (no params needed)."""
    labels = [0] * (size * size)
    for region_id, box in enumerate(region_map_for(size)):
        for row, col in box:
            labels[(row - 1) * size + (col - 1)] = region_id
    return labels


def _enabled_blocks(
    puzzle_data: dict[str, object], type_: int
) -> Iterator[dict[Any, Any]]:
    """Every enabled constraint block of one `type` from the link, in wire
    order — the shared front the per-type decoders (XV, kropki, cage) and
    `_regions_matrix` all iterate behind. Folds the three guards
    every decoder needs: a non-list `constraints` yields nothing, a non-dict
    block is skipped, and a `disabled` block is skipped (the setter switched it
    off, so
    it is not part of the puzzle even for a type gridfind decodes). `Any` in the
    element type keeps the decoded-JSON boundary, as elsewhere in this module."""
    blocks = puzzle_data.get("constraints", [])
    if not isinstance(blocks, list):
        return
    for block in blocks:
        if (
            isinstance(block, dict)
            and block.get("type") == type_
            and block.get("disabled") is not True
        ):
            yield block


def _warn_dropped_negative(block: dict[str, Any], label: str) -> None:
    """Warn to stderr when a kropki/XV `block` carries a non-empty `negative`
    list: gridfind models only the positive clues, so the verdict
    is computed without the negative rule and the drop must never be silent."""
    negative = block.get("negative")
    if isinstance(negative, list) and negative:
        print(
            f"warning: ignoring {label} negative constraint "
            "— verdict computed without it",
            file=sys.stderr,
        )


def _edge_to_pair(edge: int, size: int) -> tuple[str, str]:
    """An XV/kropki `edge` integer decoded to its two orthogonally-adjacent
    cell addresses, the primitive shared by the XV and
    white-kropki decoders.

    Edges are enumerated in row-major blocks of `2 * size`, one block per
    0-indexed row `r0`: within a block, offset `1..size-1` is a horizontal
    (left/right) pair starting `r0`, and offset `size..2*size-1` is a
    vertical (up/down) pair starting `r0` — the two closed-form formulas
    (`edge = 2N*r0 + c0 + 1` horizontal, `edge = 2N*r0 + c0 + N` vertical)
    inverted by `divmod`. Oracle-verified against a real link: X @ 70
    = R4C8/R5C8, V @ 103 = R6C5/R7C5 (vertical), kropki @ 75 = R5C3/R5C4, @
    132 = R8C6/R8C7 (horizontal), all on a 9x9 board.

    Raises `ValueError` when `edge` names no in-bounds pair on a `size`x`size`
    board (an out-of-range offset, or a row with no room for the pair)."""
    block = 2 * size
    r0, offset = divmod(edge, block)
    if 1 <= offset <= size - 1 and 0 <= r0 <= size - 1:
        c0 = offset - 1
        return cell_address(r0 + 1, c0 + 1), cell_address(r0 + 1, c0 + 2)
    if size <= offset <= block - 1 and 0 <= r0 <= size - 2:
        c0 = offset - size
        return cell_address(r0 + 1, c0 + 1), cell_address(r0 + 2, c0 + 1)
    msg = (
        f"non-classic link: edge {edge!r} does not name a valid cell pair "
        f"on a {size}x{size} board"
    )
    raise ValueError(msg)


def _edge_clue_constraints(
    puzzle_data: dict[str, object],
    size: int,
    type_: int,
    build_clue: Callable[[object, str, str], Constraint],
) -> list[Constraint]:
    """The shared decode walk behind the edge-clue types — XV, white-kropki,
    black-kropki — which share one wire shape (`clues: [{value, edge}],
    negative: [...]`). Every enabled `type_` block: each clue's `edge` decodes
    to its orthogonally-adjacent pair via `_edge_to_pair`, then
    `build_clue(value, a, b)` turns the clue's raw `value` and that pair into
    one `Constraint`. A `disabled` block is skipped entirely; a non-empty
    `negative` list is warn-and-dropped to stderr while its positive clues
    still decode. `build_clue` carries the single per-type variation — an
    alias lookup, a `diff`, a ratio `k`."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, type_):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        for clue in clues:
            a, b = _edge_to_pair(clue["edge"], size)
            decoded.append(build_clue(clue["value"], a, b))
        _warn_dropped_negative(block, DECODER_REGISTRY[type_].name)
    return decoded


def _xv_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 202` XV clues as aliased group-sum `Constraint`s: `value`
    selects the existing `x`/`v` alias (10/5), or the link is refused — no
    other value names an XV sum. See `_edge_clue_constraints` for the walk."""

    def build(value: object, a: str, b: str) -> Constraint:
        # The XV wire value is a JSON number; the cast satisfies the int-keyed
        # lookup, and a non-int value simply misses it and raises below.
        alias = _XV_ALIASES.get(cast("int", value))
        if alias is None:
            msg = (
                f"non-classic link: XV clue value {value!r} is neither X (10) nor V (5)"
            )
            raise ValueError(msg)
        return Constraint(alias, params={"cells": [a, b]})

    return _edge_clue_constraints(puzzle_data, size, _XV_TYPE, build)


def _kropki_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 200` white-kropki clues as `pair-difference` `Constraint`s:
    `value` is the target difference passed verbatim as `diff` — a labelled
    non-1 dot is honored at that value, never coerced to the consecutive
    default. `type 201` (black/ratio) has its own handler. See
    `_edge_clue_constraints` for the walk."""

    def build(value: object, a: str, b: str) -> Constraint:
        return Constraint("pair-difference", params={"cells": [a, b], "diff": value})

    return _edge_clue_constraints(puzzle_data, size, _KROPKI_WHITE_TYPE, build)


def _black_kropki_constraints(
    puzzle_data: dict[str, object], size: int
) -> list[Constraint]:
    """The `type 201` black-kropki clues as `pair-ratio` `Constraint`s: `value`
    is the target integer ratio `k`, honored verbatim — a labelled non-2 dot
    is never coerced to 2. `value` must be an int (`_as_int`); a non-integer
    ratio raises `ValueError` at decode rather than modeling a wrong verdict.
    See `_edge_clue_constraints` for the walk."""

    def build(value: object, a: str, b: str) -> Constraint:
        k = _as_int(value, "black-kropki value")
        return Constraint("pair-ratio", params={"cells": [a, b], "k": k})

    return _edge_clue_constraints(puzzle_data, size, _KROPKI_BLACK_TYPE, build)


def _address(index: int, size: int) -> str:
    """The row-major address of a raw cell `index` on a `size`-wide board: index
    `18` on a 9-board is R3C1. The single home for SudokuMaker's `i // N`, `i % N`
    scheme, shared by givens, cages, and thermometers."""
    return cell_address(index // size + 1, index % size + 1)


def _addresses(indices: Iterable[int], size: int) -> list[str]:
    """`_address` mapped over a cell-index list, order preserved — so a thermo
    path keeps bulb-first order and a cage's cells read row-major."""
    return [_address(i, size) for i in indices]


def _killer_cage(addresses: list[str], total: int | None) -> list[Constraint]:
    """A killer cage over `addresses`: always a no-repeats `cage`, plus a
    `group-sum` carrying `total` when a total is present (spec #240). A zero or
    `None` total is no total — the cage stands alone."""
    decoded = [Constraint("cage", params={"cells": addresses})]
    if total:
        decoded.append(
            Constraint("group-sum", params={"cells": addresses, "sum": total})
        )
    return decoded


def _cage_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 301` killer cages as `Constraint`s: each cage's raw `cells`
    indices map row-major to addresses (`_addresses`), so `[18, 19]` on a
    9-board is R3C1/R3C2. Every cage decodes to a no-repeats `cage`; a positive
    `value` additionally decodes a `group-sum` over the same cells (spec #240) —
    `0` (SudokuMaker's own no-sum cage) decodes to `cage` alone, exactly as an
    absent `value`. A `disabled` block is skipped entirely; an empty `cages`
    list adds nothing."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _CAGE_TYPE):
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


_CosmeticCageNameKind = Literal["ordinary", "doubler", "s-cell", "unrecognized"]


def _cosmetic_cage_name_kind(name: object) -> _CosmeticCageNameKind:
    """Classify a `type 2001` block's top-level `name` (spec #324) into one of
    four kinds: `"ordinary"` (absent/blank, or a decorative `Sum`/`Killer`
    label on a genuine cage — `_NAMED_KILLER_CAGE_LABELS`), `"doubler"` (a
    `Doubler` position marker — `_DOUBLER_MARKER_LABELS`), `"s-cell"` (an
    `S-cell`/`Schrödinger` position marker — `_SCELL_MARKER_LABELS`), or
    `"unrecognized"` (a name `decode_link` cannot answer for). Matching is
    case-insensitive and trimmed."""
    if not isinstance(name, str) or not name.strip():
        return "ordinary"
    normalized = name.strip().lower()
    if normalized in _NAMED_KILLER_CAGE_LABELS:
        return "ordinary"
    if normalized in _DOUBLER_MARKER_LABELS:
        return "doubler"
    if normalized in _SCELL_MARKER_LABELS:
        return "s-cell"
    return "unrecognized"


def is_scell_marker_name(name: object) -> bool:
    """True when a `type 2001` block's top-level `name` reads as the
    `S-cell`/`Schrödinger` marker (`_cosmetic_cage_name_kind`'s `"s-cell"`
    branch), public for a dev tool that needs to recognize a marker block
    without decoding the whole link — `scripts/verify_links.py`'s
    `fill_witness` uses it to find the cage whose `value` a solved S-cell pair
    must be stamped back onto (spec #349)."""
    return _cosmetic_cage_name_kind(name) == "s-cell"


def is_doubler_marker_name(name: object) -> bool:
    """True when a `type 2001` block's top-level `name` reads as the `Doubler`
    modifier marker (`_cosmetic_cage_name_kind`'s `"doubler"` branch), public
    for the same dev-tool need as `is_scell_marker_name` — `verify_links`'s
    `fill_witness` finds the Doubler block to mark every solver-found modifier
    cell in its cage."""
    return _cosmetic_cage_name_kind(name) == "doubler"


@dataclass(frozen=True)
class _CosmeticCageDecode:
    """The `Constraint`s and `ModifierDirective`s one `type 2001` block
    decodes to — an ordinary (unnamed, or `Sum`/`Killer`-labelled) block
    contributes killer-cage constraints, a `Doubler`-marked block contributes
    modifier directives instead, and `concat` folds a link's worth of blocks
    into the two lists `decode_link` reads."""

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


def _cosmetic_cage_constraints(
    puzzle_data: dict[str, object],
    size: int,
    *,
    ignore_unknown_named_cages: bool = False,
) -> _CosmeticCageDecode:
    """The `type 2001` cosmetic-cage blocks decoded per their top-level `name`
    (`_cosmetic_cage_name_kind`, spec #324): an ordinary block graduates to
    killer-cage `Constraint`s (ADR-0008) exactly as before — cells and value
    nest under `cages`, the same wire shape as a `type 301` block, each cage's
    raw `cells` indices mapping row-major to addresses, every non-disabled
    cage emitting a no-repeats `cage` plus a `group-sum` when its numeric
    non-zero string `value` carries a total (spec #240). A `Doubler`-marked
    block instead emits one `ModifierDirective(is_modifier=True)` per cell it
    contains and **no** `cage`/`group-sum` — the block's `cages` still supply
    the cell list, just not a killer rule. An `S-cell`/`Schrödinger`-marked
    block emits nothing here: its cells become S-cell working-state directives
    in the per-cell decode pass (`_scell_marker_values` gathers them, cage
    `value` and all), not a cage rule. An unrecognized name refuses the
    whole block rather than decoding some cages under an unsound reading,
    unless `ignore_unknown_named_cages` downgrades the refusal to
    strip-and-honor as an ordinary cage. A `disabled` block is skipped
    entirely; an empty `cages` list adds nothing."""
    decoded: list[_CosmeticCageDecode] = []
    for block in _enabled_blocks(puzzle_data, _COSMETIC_CAGE_TYPE):
        kind = _cosmetic_cage_name_kind(block.get("name"))
        if kind == "unrecognized":
            if not ignore_unknown_named_cages:
                msg = f"non-classic link: unrecognized named cage {block['name']!r}"
                raise ValueError(msg)
            kind = "ordinary"
        if kind == "s-cell":
            continue
        cages = cast("list[dict[str, Any]]", block.get("cages", []))
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


def _is_scell_block(block: dict[Any, Any]) -> bool:
    """True when a `type 2001` block is named `S-cell`/`Schrödinger`
    (`_SCELL_MARKER_LABELS`, via `_cosmetic_cage_name_kind`). The one predicate
    both S-cell channels share, so presence and pinning agree on the label set
    by construction: `_has_scell_marker_block` reads it for enablement by
    presence, `_scell_marker_values` for pinning by membership (ADR-0014)."""
    return _cosmetic_cage_name_kind(block.get("name")) == "s-cell"


def _scell_marker_values(
    puzzle_data: dict[str, object], size: int
) -> dict[str, object]:
    """Every cell address declared an S-cell by a `type 2001` cosmetic-cage
    block named `S-cell`/`Schrödinger` (`_SCELL_MARKER_LABELS`), mapped to its
    marker cage's own raw `value` (spec #349) — the pair/half/bare source
    `_decode_cell` reads for that address. A multi-cell cage's `value` applies
    uniformly to every cell it contains (CONTEXT.md `marker cage`). The
    mapping's key set doubles as the address set that routes a cell through the
    S-cell branch — the *membership* channel that pins known S-cells. It does
    not enable the mode: `_has_scell_marker_block` reads block *presence* for
    that, so an empty block enables Schrödinger with this mapping empty
    (ADR-0014). A `disabled` block contributes nothing, exactly as its cage
    rule would not."""
    return {
        address: cage.get("value")
        for block in _enabled_blocks(puzzle_data, _COSMETIC_CAGE_TYPE)
        if _is_scell_block(block)
        for cage in cast("list[dict[str, Any]]", block.get("cages", []))
        for address in _addresses(cage["cells"], size)
    }


def _has_scell_marker_block(puzzle_data: dict[str, object]) -> bool:
    """True when an enabled `type 2001` cosmetic-cage block is named
    `S-cell`/`Schrödinger` (`_SCELL_MARKER_LABELS`), regardless of whether it
    names any cells. This block *presence* enables Schrödinger mode (ADR-0014):
    the domain widens to `0…N` and a `schrodinger` constraint stands up, giving
    every cell the `is_s` freedom the solver discovers S-cells with. An empty
    block means "discover them all"; a block that names cells additionally
    pins those as known S-cells (`_scell_marker_values`)."""
    return any(
        _is_scell_block(block)
        for block in _enabled_blocks(puzzle_data, _COSMETIC_CAGE_TYPE)
    )


# The order `colorize_marker_cages` claims `_MARKER_COLOR_PALETTE` slots in
# when a link carries more than one marker type — S-cell first, so it always
# wins red over Doubler on a mixed link.
_MARKER_KIND_PRIORITY: tuple[_CosmeticCageNameKind, ...] = ("s-cell", "doubler")


def colorize_marker_cages(document: dict[str, object]) -> dict[str, object]:
    """`document` with every named marker cage's `type 2001` block stamped
    with a display color at `style.cage.color` — the field SudokuMaker renders a
    cosmetic cage's fill from — on a copy; `document` itself is untouched. The
    color a marker type gets depends on which marker types the
    *link* actually carries, not a fixed per-type constant: the marker types
    present among `document`'s enabled `type 2001` blocks are ranked by
    `_MARKER_KIND_PRIORITY` and assigned `_MARKER_COLOR_PALETTE` slots in that
    order, so a link with only one marker type always colors it red
    (`_MARKER_COLOR_PALETTE[0]`), whichever type it is, while a link mixing
    types gives S-cell red and Doubler the next slot. An ordinary (unnamed or
    Sum/Killer-labelled) cosmetic-cage block, an unrecognized name, and every
    other constraint type ride through uncolored. The written field is
    display-only: `decode_link` never reads a cosmetic-cage block's `style`,
    so a decode of the result agrees with a decode of `document`."""
    colored: dict[str, object] = json.loads(json.dumps(document))
    puzzle_data = cast("dict[str, object]", colored["puzzle"])
    blocks = list(_enabled_blocks(puzzle_data, _COSMETIC_CAGE_TYPE))
    present_kinds = {_cosmetic_cage_name_kind(block.get("name")) for block in blocks}
    color_of_kind = dict(
        zip(
            (kind for kind in _MARKER_KIND_PRIORITY if kind in present_kinds),
            _MARKER_COLOR_PALETTE,
            strict=False,
        )
    )
    for block in blocks:
        color = color_of_kind.get(_cosmetic_cage_name_kind(block.get("name")))
        if color is not None:
            style = cast("dict[str, Any]", block.setdefault("style", {}))
            cage_style = cast("dict[str, Any]", style.setdefault("cage", {}))
            cage_style["color"] = color
    return colored


def _thermo_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 300` thermometers as `thermo` `Constraint`s: each path's raw indices
    map row-major to addresses, order
    preserved (bulb first) — order is the whole point of a line, unlike
    `cage`'s unordered `cells`. `slow` rides through verbatim onto every path
    in the block. A `disabled` block is skipped entirely; an empty
    `thermometers` list adds nothing. The cosmetic `style` object is
    ignored."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _THERMO_TYPE):
        slow = bool(block.get("slow", False))
        paths = cast("list[list[int]]", block.get("thermometers", []))
        for path in paths:
            addresses = _addresses(path, size)
            params: dict[str, object] = {"path": addresses, "slow": slow}
            decoded.append(Constraint("thermo", params=params))
    return decoded


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
    by hand for their extra ignore-flag argument and richer
    `_CosmeticCageDecode` return; `type 1`'s regions live behind
    `_regions_constraints` like every other generically-dispatched handler),
    `live_keys` are the payload keys that mark this type's wire shape as
    carrying a real rule (read by `has_live_data`, generalized to unmodeled
    types too), `name` labels it in the decoder's own warnings, and
    `setter_doc` carries the setter-facing reference-table facts for this
    type — `None` for a structural row (`type 0`/`type 1`) that no setter
    draws directly."""

    handler: Callable[[dict[str, object], int], list[Constraint]] | None
    live_keys: tuple[str, ...]
    name: str
    setter_doc: SetterDoc | None


# The one table wire-type -> (handler, live-data payload keys, display name):
# `decode_link` dispatches through it, `_warn_on_dropped_constraints` treats
# its keys as the already-modeled ruleset, and `has_live_data` reads its
# `live_keys` — adding a link type is one row here, not three hand-synced
# call sites.
DECODER_REGISTRY: dict[int, DecodedType] = {
    0: DecodedType(handler=None, live_keys=(), name="givens", setter_doc=None),
    1: DecodedType(
        handler=_regions_constraints, live_keys=(), name="regions", setter_doc=None
    ),
    _KROPKI_WHITE_TYPE: DecodedType(
        handler=_kropki_constraints,
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
    _KROPKI_BLACK_TYPE: DecodedType(
        handler=_black_kropki_constraints,
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
    _XV_TYPE: DecodedType(
        handler=_xv_constraints,
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
    _CAGE_TYPE: DecodedType(
        handler=_cage_constraints,
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
    _COSMETIC_CAGE_TYPE: DecodedType(
        handler=None,
        live_keys=("cages",),
        name="cosmetic-cage",
        setter_doc=SetterDoc(
            display_name="Cosmetic Cage",
            wire_block="type 2001 {cages:[{value:str, cells}], name?,"
            " style?} — value is a string; a top-level name may mark the"
            " block as a variant declaration.",
            decode_result="name classifies the block: absent/Sum/Killer"
            " decodes as a killer cage (a numeric non-zero string value"
            " graduates to a group-sum); Doubler emits per-cell modifier"
            " directives; S-cell/Schrödinger/Schrodinger infers"
            " Schrödinger-ness and routes its cells through the per-cell"
            " S-cell branch.",
            verdict="Accept a recognized name. An unrecognized name raises"
            " ValueError, downgradable to strip-and-honor via"
            " ignore_unknown_named_cages. disabled blocks are skipped.",
        ),
    ),
    _THERMO_TYPE: DecodedType(
        handler=_thermo_constraints,
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
}

# The union of every registered type's live-data keys, order-preserved and
# deduped — `has_live_data` checks these instead of a hand-copied list that
# happened to match what the decoders above read.
_LIVE_LIST_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys(key for entry in DECODER_REGISTRY.values() for key in entry.live_keys)
)


def _warn_on_dropped_constraints(puzzle_data: dict[str, object]) -> None:
    """Ignore every constraint gridfind doesn't model, warning to
    stderr for any that carries live data — so a verdict is never silently
    computed under a smaller ruleset than the link states.

    Types in `DECODER_REGISTRY` — 0 givens, 1 regions, 200
    white-kropki, 201 black-kropki, 202 XV, 300 thermo, 301 killer-cage, 2001
    cosmetic-cage — are modeled elsewhere and pass through. A `disabled`
    constraint is skipped first with no warning: the setter switched it off,
    so it is not part of
    the puzzle even for a type gridfind knows how to decode. A remaining
    enabled unmodeled constraint is inert (empty or cosmetic-only payload) and
    dropped quietly, or active (a live clue/negative list or a populated
    group) and dropped loudly, named by its `definition.name` when the link
    carries one. Honoring a specific variant rather than dropping it is the
    opt-in variant-decoder path; each variant still warns on the
    part it can't model (a kropki/XV `negative` list), fired from its own
    decoder instead.

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
        if has_live_data(constraint):
            name = constraint_name(constraint)
            named = f" {name!r}" if name is not None else ""
            msg = (
                f"warning: ignoring unmodeled constraint{named} (type {kind!r}) "
                "— verdict computed without it"
            )
            print(msg, file=sys.stderr)


def has_live_data(constraint: dict[Any, Any]) -> bool:
    """True when an enabled, unmodeled constraint carries data that would emit
    a rule: a non-empty list under one of `DECODER_REGISTRY`'s `live_keys`
    (`clues`/`negative`/`cages`), or a group holding real cells
    under `input.groups`. Empty payloads and cosmetic-only `lines` are inert.

    `cages` is a killer-cage block's (`type 301`) payload. It is decoded now,
    so `_warn_on_dropped_constraints` skips it — this entry marks
    a populated cage block `active` for `scripts/inspect_link.py`, exactly as
    the `clues` entry does for decoded XV (`type 202`): a decoded variant still
    carries a live rule the dev tool must not report as inert. A `type 2001`
    cosmetic cage carries its cages under the same `cages` key, so a populated
    cosmetic block is `active` on the same scan.

    Public so `scripts/inspect_link.py` classifies constraints against the same
    predicate the decoder drops by. `Any` keeps the decoded-JSON
    boundary type (a dict narrowed from the untyped payload), as `decode_link`
    does for `puzzle_data`."""
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
