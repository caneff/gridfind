"""Decode a SudokuMaker share link into gridfind's `Puzzle` + `WorkingState`.

Its core function, `decode_link`, mirrors `puzzle.py`'s schema-only role: it
strips the `?puzzle=` payload, lz-string-decompresses it, and maps the
`formatVersion 1.5.0` JSON to the model per the confirmed field-by-field map in
`docs/research/sudoku-link-formats.md` §4a/§4b. Size, digit
domain, and regions are read from the link's own fields — `width`/`size` (else
`isqrt(len(cells))`), `minDigit`/`maxDigit` (else `1..N`), and the `type 1`
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
thermo) — is one row in `DECODER_REGISTRY`: `decode_link`'s
dispatch, the
dropped-constraint warning path, and `has_live_data`'s active/inert check all
read that one table instead of each restating "type N is decoded" by hand.

The `schrodinger`/`reading` keywords declare a
SudokuMaker-Schrödinger link explicitly rather than sniffing one: they relax
the `minDigit` guard to read the widened domain, decode each cell's red
`colors` bit and center marks into a Schrödinger working-state directive
(CONTEXT.md `schrodinger` layer). Every link — Schrödinger or not — ignores
the unmodeled constraint types and `disabled` blocks a real link carries,
warning to stderr only when a dropped one carried live data.

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
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from math import isqrt
from typing import Any, cast

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
    Placement,
    Puzzle,
    SCellPin,
    SDirective,
    SingletonPin,
    WorkingState,
)

# The only reading built so far — sum-valued and
# positional are future values of the same flag, refused until then.
_CLASSIC_READING = "classic"

# `colors` is an OR of palette-color bits; red — SudokuMaker's S-cell
# convention — is bit value 2, never `colors == 2`
# since a cell may carry other decorative colors too.
_RED_BIT = 2

# An S-cell pin's center marks are exactly two digits; fewer or more are the
# looser bare/half directives instead.
_SCELL_PIN_MARKS = 2

# type 202 is XV: `clues: [{value, edge}], negative:
# [...]`. `value` selects the existing pair-sum alias — 10 is X, 5 is V
# — never a raw `sum`, so a puzzle carrying both an XV clue and
# a literal pair-sum on the same cells still hits the alias's own
# fixed-param conflict check in `expand_constraints`. Read off
# `gridfind.layers.ALIAS_REGISTRY` rather than restated here — the
# sum each alias fixes is stated once, in the registry that also builds it.
_XV_TYPE = 202
_XV_ALIASES: dict[int, str] = {
    cast("int", fixed["sum"]): alias
    for alias, (canonical, fixed) in ALIAS_REGISTRY.items()
    if canonical == "pair-sum" and "sum" in fixed
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
# positive `value` is the killer sum, honored by the `cage` layer
# — 0 is SudokuMaker's own no-sum cage, region-only exactly as `value` absent.
_CAGE_TYPE = 301

# type 300 is a thermometer block: `slow: bool,
# thermometers: [[cell indices, ordered, bulb first], …]`. Each path becomes
# its own `thermo` Constraint; `slow` rides through onto every path in the
# block. The strict-vs-non-strict split is the `thermo` layer's concern, not
# the decoder's.
_THERMO_TYPE = 300


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
    link: str, *, schrodinger: bool = False, reading: str = _CLASSIC_READING
) -> tuple[Puzzle, WorkingState]:
    """Map a SudokuMaker `?puzzle=` link (or a bare payload) to a square-N
    `Puzzle` + `WorkingState`, sizing the board and domain from the link
    itself. Raises `ValueError` on a link gridfind can't answer.

    `schrodinger` **declares** the SudokuMaker-Schrödinger variant — it is never
    inferred from the link. It reads the link's
    `minDigit` into `Board.values` under the classic reading (`k = 1` extra
    digit: `range(minDigit, minDigit + size + 1)`), relaxes the classic-only
    guard, synthesizes a bare `{type: schrodinger}` constraint, and decodes
    each cell's red bit + center marks into a Schrödinger working-state
    directive instead of a plain placement/candidate. `reading` names the
    S-cell interpretation; only `"classic"` is built, so any other value is
    refused."""
    if schrodinger and reading != _CLASSIC_READING:
        msg = f"unsupported schrodinger reading: {reading!r}"
        raise ValueError(msg)
    puzzle_data: Any = decode_document(link)["puzzle"]
    size = _board_size(puzzle_data)
    _warn_on_dropped_constraints(puzzle_data)

    cells = puzzle_data["cells"]
    givens: list[Given] = []
    places: list[Placement] = []
    candidates: list[Candidate] = []
    s_directives: list[SDirective] = []
    domain = (
        _schrodinger_domain(puzzle_data, size)
        if schrodinger
        else _digit_domain(puzzle_data, size)
    )
    for i, cell in enumerate(cells):
        address = cell_address(i // size + 1, i % size + 1)
        if schrodinger:
            _decode_schrodinger_cell(
                cell, address, domain, givens, s_directives, candidates
            )
        elif "value" in cell:
            if cell.get("given"):
                givens.append(Given(address, cell["value"]))
            else:
                places.append(Placement(address, cell["value"]))
        elif "candidates" in cell:
            digits = frozenset(d for d in domain if cell["candidates"] & (1 << d))
            candidates.append(Candidate(address, digits))
        # cornerPencilMarks, colors, and {} carry nothing gridfind can represent.

    # SudokuMaker leaves rows/cols implicit under `type 0`; gridfind makes both
    # explicit — rows/cols always bare, everything else via DECODER_REGISTRY.
    constraints = [Constraint("rows-distinct"), Constraint("cols-distinct")]
    for decoded_type in DECODER_REGISTRY.values():
        if decoded_type.handler is not None:
            constraints.extend(decoded_type.handler(puzzle_data, size))
    board = Board(size=size, values=domain)
    if schrodinger:
        constraints.append(Constraint("schrodinger"))

    puzzle = Puzzle(board=board, constraints=tuple(constraints), givens=tuple(givens))
    state = WorkingState(
        places=tuple(places),
        candidates=tuple(candidates),
        s_directives=tuple(s_directives),
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
    else `isqrt(len(cells))` — the classic link, which omits all three, lands
    on `isqrt(81) = 9`. The shape must be square (`rows == cols`) and its cell
    count must match (`rows * cols == len(cells)`); a non-square link or a
    size/count mismatch is refused with its own reason."""
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
        rows = cols = isqrt(count)
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
    `minDigit` (defaulting to 1 when absent — the link carries no `maxDigit` or
    `digitCount`) through `minDigit + N`, the
    `k = 1` extra digit the classic Schrödinger rule derives, not reads."""
    min_digit = _as_int(puzzle_data.get("minDigit", 1), "minDigit")
    return range(min_digit, min_digit + size + 1)


def write_s_cell(cell: dict[str, Any], a: int, b: int) -> None:
    """Write an S-cell's two-digit pin into `cell` on the wire channel
    `_decode_schrodinger_cell` reads a `SCellPin` back from: set the `_RED_BIT`
    in `colors` (S-cell-ness, OR-ed in so any decorative colors survive) and
    set both digits in the `candidates` bitmask (the two center marks). The
    inverse of that decode's pin branch."""
    cell["colors"] = cell.get("colors", 0) | _RED_BIT
    cell["candidates"] = (1 << a) | (1 << b)


def _decode_schrodinger_cell(
    cell: dict[str, Any],
    address: str,
    domain: range,
    givens: list[Given],
    s_directives: list[SDirective],
    candidates: list[Candidate],
) -> None:
    """One cell's directive under `--schrodinger`.
    A given stays literal (`Given`, unchanged from classic). Otherwise a red
    cell (`colors` bit 2) carries S-cell-ness; its center-mark count picks the
    digit axis: exactly two marks is an S-cell pin, exactly one a half S-cell,
    zero or three-plus a bare S-cell (any marks riding along as ordinary
    candidates). A non-red cell holding a value is a singleton pin — the
    Schrödinger analog of a placement, carrying the extra "not an S-cell"
    claim. A red cell holding a value is a decode-time contradiction (is-S
    and a settled singleton can't both hold) and is refused as `ValueError`,
    not `MalformedPuzzleError` — this is the decoder finding a link it can't
    represent, not `verdict` finding a puzzle it can't answer (module
    doctrine)."""
    if cell.get("given"):
        givens.append(Given(address, cell["value"]))
        return
    red = bool(cell.get("colors", 0) & _RED_BIT)
    if "value" in cell:
        if red:
            msg = f"non-classic link: red cell {address} also holds a value"
            raise ValueError(msg)
        s_directives.append(SingletonPin(address, cell["value"]))
        return
    if red:
        marks = frozenset(d for d in domain if cell.get("candidates", 0) & (1 << d))
        if len(marks) == _SCELL_PIN_MARKS:
            s_directives.append(SCellPin(address, marks))
        elif len(marks) == 1:
            (digit,) = marks
            s_directives.append(HalfSCell(address, digit))
        else:
            s_directives.append(BareSCell(address))
            if marks:
                candidates.append(Candidate(address, marks))
        return
    if "candidates" in cell:
        digits = frozenset(d for d in domain if cell["candidates"] & (1 << d))
        candidates.append(Candidate(address, digits))
    # cornerPencilMarks, non-red colors, and {} carry nothing gridfind can
    # represent — same as the classic path.


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


def _xv_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 202` XV clues as aliased pair-sum `Constraint`s: each clue's `value`
    selects the existing `x`/`v` alias (10/5) and
    its `edge` decodes to the adjacent cell pair via `_edge_to_pair`. A
    `disabled` block is skipped entirely; a non-empty `negative` list is
    warn-and-dropped to stderr while its positive clues still
    decode."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _XV_TYPE):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        for clue in clues:
            value = clue["value"]
            alias = _XV_ALIASES.get(value)
            if alias is None:
                msg = (
                    f"non-classic link: XV clue value {value!r} is neither "
                    "X (10) nor V (5)"
                )
                raise ValueError(msg)
            a, b = _edge_to_pair(clue["edge"], size)
            decoded.append(Constraint(alias, params={"cells": [a, b]}))
        _warn_dropped_negative(block, DECODER_REGISTRY[_XV_TYPE].name)
    return decoded


def _kropki_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 200` white-kropki clues as `pair-difference` `Constraint`s:
    each clue's `edge` decodes to the adjacent cell pair via
    `_edge_to_pair`, and its `value` is the target difference passed verbatim
    as `diff` — a labelled non-1 dot is honored at that value, never coerced to
    the consecutive default. Only `type 200` (white/difference) decodes here;
    `type 201` (black/ratio) has its own `_black_kropki_constraints` handler.
    A `disabled` block is skipped entirely; a non-empty `negative` list is
    warn-and-dropped to stderr while its positive clues still
    decode."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _KROPKI_WHITE_TYPE):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        for clue in clues:
            a, b = _edge_to_pair(clue["edge"], size)
            params = {"cells": [a, b], "diff": clue["value"]}
            decoded.append(Constraint("pair-difference", params=params))
        _warn_dropped_negative(block, DECODER_REGISTRY[_KROPKI_WHITE_TYPE].name)
    return decoded


def _black_kropki_constraints(
    puzzle_data: dict[str, object], size: int
) -> list[Constraint]:
    """The `type 201` black-kropki clues as `pair-ratio` `Constraint`s: each clue's
    `edge` decodes to the adjacent cell pair
    via `_edge_to_pair`, and its `value` is the target integer ratio `k`,
    honored verbatim — a labelled non-2 dot is never coerced to 2. `value`
    must be an int (`_as_int`); a non-integer ratio raises `ValueError` at
    decode rather than modeling a wrong verdict. A `disabled` block is
    skipped entirely; a non-empty `negative` list is warn-and-dropped to
    stderr while its positive clues still decode."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _KROPKI_BLACK_TYPE):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        for clue in clues:
            a, b = _edge_to_pair(clue["edge"], size)
            k = _as_int(clue["value"], "black-kropki value")
            decoded.append(Constraint("pair-ratio", params={"cells": [a, b], "k": k}))
        _warn_dropped_negative(block, DECODER_REGISTRY[_KROPKI_BLACK_TYPE].name)
    return decoded


def _cage_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 301` killer cages as `cage` `Constraint`s (killer sum): each cage's raw
    `cells` indices map row-major to
    addresses — the same `i // N`, `i % N` scheme givens use — so `[18, 19]`
    on a 9-board is R3C1/R3C2. A positive `value` rides through as the `cage`
    layer's `value` param, which enforces it as the killer sum; `0`
    (SudokuMaker's own no-sum cage) decodes cells-only, region-only exactly
    as an absent `value`. A `disabled` block is skipped entirely; an empty
    `cages` list adds nothing."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _CAGE_TYPE):
        cages = cast("list[dict[str, Any]]", block.get("cages", []))
        for cage in cages:
            cells = [cell_address(i // size + 1, i % size + 1) for i in cage["cells"]]
            params: dict[str, object] = {"cells": cells}
            value = cage.get("value", 0)
            if value > 0:
                params["value"] = value
            decoded.append(Constraint("cage", params=params))
    return decoded


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
            addresses = [cell_address(i // size + 1, i % size + 1) for i in path]
            params: dict[str, object] = {"path": addresses, "slow": slow}
            decoded.append(Constraint("thermo", params=params))
    return decoded


@dataclass(frozen=True)
class DecodedType:
    """One SudokuMaker wire-type the decoder recognizes, one row wide: `handler` builds
    this type's `Constraint`s from the link (`None`
    for a structural type with nothing to build — a bare `type 0` is just the
    unconditional rows/cols, and `type 1`'s regions live behind
    `_regions_constraints` like every other handler), `live_keys` are the
    payload keys that mark this type's wire shape as carrying a real rule
    (read by `has_live_data`, generalized to unmodeled types too), and `name`
    labels it in the decoder's own warnings.
    """

    handler: Callable[[dict[str, object], int], list[Constraint]] | None
    live_keys: tuple[str, ...]
    name: str


# The one table wire-type -> (handler, live-data payload keys, display name):
# `decode_link` dispatches through it, `_warn_on_dropped_constraints` treats
# its keys as the already-modeled ruleset, and `has_live_data` reads its
# `live_keys` — adding a link type is one row here, not three hand-synced
# call sites.
DECODER_REGISTRY: dict[int, DecodedType] = {
    0: DecodedType(handler=None, live_keys=(), name="givens"),
    1: DecodedType(handler=_regions_constraints, live_keys=(), name="regions"),
    _KROPKI_WHITE_TYPE: DecodedType(
        handler=_kropki_constraints,
        live_keys=("clues", "negative"),
        name="white-kropki",
    ),
    _KROPKI_BLACK_TYPE: DecodedType(
        handler=_black_kropki_constraints,
        live_keys=("clues", "negative"),
        name="black-kropki",
    ),
    _XV_TYPE: DecodedType(
        handler=_xv_constraints, live_keys=("clues", "negative"), name="XV"
    ),
    _CAGE_TYPE: DecodedType(
        handler=_cage_constraints, live_keys=("cages",), name="killer-cage"
    ),
    _THERMO_TYPE: DecodedType(
        handler=_thermo_constraints, live_keys=("thermometers",), name="thermo"
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
    white-kropki, 201 black-kropki, 202 XV, 300 thermo, 301 killer-cage — are
    modeled elsewhere and pass through. A `disabled` constraint is skipped
    first with no warning: the setter switched it off, so it is not part of
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
    carries a live rule the dev tool must not report as inert.

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
