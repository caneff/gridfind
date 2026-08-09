"""Decode a SudokuMaker share link into gridfind's `Puzzle` + `WorkingState`.

One pure function, `decode_link`, mirroring `puzzle.py`'s schema-only role: it
strips the `?puzzle=` payload, lz-string-decompresses it, and maps the
`formatVersion 1.5.0` JSON to the model per the confirmed field-by-field map in
`docs/research/sudoku-link-formats.md` §4a (issue #54). Classic 9x9 domain
only — a non-classic link (a variant `minDigit`/`maxDigit` domain, an unknown
ruleset, a non-81 grid) is rejected with `ValueError` rather than mis-decoded
into a confident wrong verdict. A `type 1` jigsaw regions matrix decodes
instead of being refused (issue #125): it rides straight onto the
`regions-distinct` constraint's `params["regions"]`, unvalidated — a malformed
matrix surfaces as `MalformedPuzzleError` from `verdict`, never from here.

The `schrodinger`/`reading` keywords (issue #143, spec #139) declare a
SudokuMaker-Schrödinger link explicitly rather than sniffing one: they relax
the `minDigit` guard to read the widened domain, decode each cell's red
`colors` bit and center marks into a Schrödinger working-state directive
(CONTEXT.md `schrodinger` layer), and ignore rather than reject the cosmetic
constraint types and `disabled` blocks a real link carries. Without the flag
every link decodes exactly as before.

Deliberately kept as `ValueError`, not folded into `MalformedPuzzleError`
(issue #107): every rejection here fires before a `Puzzle` exists at all — it
is this decoder finding a link it does not support, not gridfind finding a
puzzle it cannot answer. A `Puzzle` `decode_link` does produce is never itself
malformed; a `MalformedPuzzleError` from a *decoded* one would still surface
from `verdict`, same as it would for a hand-built `Puzzle`. Conflating the two
would cost a caller the ability to tell "this share link doesn't decode" from
"this puzzle doesn't hold together" — a distinction worth keeping since only
one of them means the *link* is bad.

No engine, no `verdict` call. Schema in, model out.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from lzstring import LZString

from gridfind.layers.board import cell_address
from gridfind.layers.regions import region_map_for
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

# The decoder is classic-9x9-only (issue #77 leaves it untouched) — its own
# constant, not the board layer's (which now derives size from the puzzle).
BOARD_SIZE = 9
CELL_COUNT = BOARD_SIZE * BOARD_SIZE
# The digit domain of a classic (1-9). Bit 0 of a candidates/corner mask is only
# meaningful for a `minDigit:0` variant, which the guard rejects (§4a) unless
# --schrodinger is given (issue #143).
_DIGITS = range(1, BOARD_SIZE + 1)

# The only reading built so far (issue #143 first light) — sum-valued and
# positional are future values of the same flag, refused until then.
_CLASSIC_READING = "classic"

# `colors` is an OR of palette-color bits; red — SudokuMaker's S-cell
# convention (spec #139 decision #138) — is bit value 2, never `colors == 2`
# since a cell may carry other decorative colors too.
_RED_BIT = 2

# An S-cell pin's center marks are exactly two digits; fewer or more are the
# looser bare/half directives instead (issue #143's encoding table).
_SCELL_PIN_MARKS = 2

# SudokuMaker leaves rows/cols implicit under `type 0`; gridfind makes all
# three explicit — rows/cols are always bare, and regions per _regions_constraint.

# The standard 3x3 box partition as SudokuMaker's flat 81-array of region ids,
# row-major — a `type 1` `regions` matrix equal to this is the classic box
# tiling (no params needed); anything else is a jigsaw partition to carry
# through verbatim (issue #125).
_CLASSIC_REGIONS = [0] * CELL_COUNT
for _region_id, _box in enumerate(region_map_for(BOARD_SIZE)):
    for _row, _col in _box:
        _CLASSIC_REGIONS[(_row - 1) * BOARD_SIZE + (_col - 1)] = _region_id


def decode_link(
    link: str, *, schrodinger: bool = False, reading: str = _CLASSIC_READING
) -> tuple[Puzzle, WorkingState]:
    """Map a SudokuMaker `?puzzle=` link (or a bare payload) to a classic 9x9
    `Puzzle` + `WorkingState`. Raises `ValueError` on a non-classic link.

    `schrodinger` **declares** the SudokuMaker-Schrödinger variant (spec #139,
    issue #143) — it is never inferred from the link. It reads the link's
    `minDigit` into `Board.values` under the classic reading (`k = 1` extra
    digit: `range(minDigit, minDigit + size + 1)`), relaxes the classic-only
    guard so cosmetic and disabled constraints are ignored rather than
    rejected, synthesizes a bare `{type: schrodinger}` constraint, and decodes
    each cell's red bit + center marks into a Schrödinger working-state
    directive instead of a plain placement/candidate. `reading` names the
    S-cell interpretation; only `"classic"` is built, so any other value is
    refused."""
    if schrodinger and reading != _CLASSIC_READING:
        msg = f"unsupported schrodinger reading: {reading!r}"
        raise ValueError(msg)
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    puzzle_data: Any = json.loads(raw)["puzzle"]
    _reject_non_classic(puzzle_data, schrodinger=schrodinger)

    cells = puzzle_data["cells"]
    givens: list[Given] = []
    places: list[Placement] = []
    candidates: list[Candidate] = []
    s_directives: list[SDirective] = []
    domain = _schrodinger_domain(puzzle_data) if schrodinger else _DIGITS
    for i, cell in enumerate(cells):
        address = cell_address(i // BOARD_SIZE + 1, i % BOARD_SIZE + 1)
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

    constraints = [
        Constraint("rows-distinct"),
        Constraint("cols-distinct"),
        _regions_constraint(puzzle_data),
    ]
    board = (
        Board(size=BOARD_SIZE, values=domain) if schrodinger else Board(size=BOARD_SIZE)
    )
    if schrodinger:
        constraints.append(Constraint("schrodinger"))

    puzzle = Puzzle(board=board, constraints=tuple(constraints), givens=tuple(givens))
    state = WorkingState(
        places=tuple(places),
        candidates=tuple(candidates),
        s_directives=tuple(s_directives),
    )
    return puzzle, state


def _schrodinger_domain(puzzle_data: dict[str, object]) -> range:
    """The board's digit domain under the classic reading: `minDigit`
    (defaulting to 1 when absent — the link carries no `maxDigit` or
    `digitCount`, per #143's verified wire format) through `minDigit + size`,
    the `k = 1` extra digit the classic Schrödinger rule derives, not reads."""
    min_digit = puzzle_data.get("minDigit", 1)
    if not isinstance(min_digit, int):
        msg = f"non-classic link: minDigit must be an int, got {min_digit!r}"
        raise ValueError(msg)
    return range(min_digit, min_digit + BOARD_SIZE + 1)


def _decode_schrodinger_cell(
    cell: dict[str, Any],
    address: str,
    domain: range,
    givens: list[Given],
    s_directives: list[SDirective],
    candidates: list[Candidate],
) -> None:
    """One cell's directive under `--schrodinger`, per #143's encoding table.
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


def _regions_constraint(puzzle_data: dict[str, object]) -> Constraint:
    """The `regions-distinct` constraint: bare for the standard 3x3 partition
    (today's classic shape, unchanged) or when `type 1` is absent, carrying
    the setter's own `params["regions"]` matrix verbatim for a jigsaw
    partition otherwise (issue #125). A `disabled: true` type-1 block is
    skipped (issue #143) — a real link may carry a disabled duplicate
    alongside the live one. Never validated here — a malformed matrix
    surfaces from `verdict`, not decode."""
    constraints = puzzle_data.get("constraints", [])
    if isinstance(constraints, list):
        for constraint in constraints:
            if (
                isinstance(constraint, dict)
                and constraint.get("type") == 1
                and not constraint.get("disabled")
            ):
                regions = constraint.get("regions")
                if regions != _CLASSIC_REGIONS:
                    return Constraint("regions-distinct", params={"regions": regions})
    return Constraint("regions-distinct")


def _reject_non_classic(
    puzzle_data: dict[str, object], *, schrodinger: bool = False
) -> None:
    """Guard the classic 9x9 boundary: refuse a variant domain, a non-81 grid,
    or an unknown ruleset (§4a). Narrows the untyped JSON as it checks — a
    shape that isn't a classic's is exactly what it rejects. A jigsaw `type 1`
    regions matrix is not rejected here (issue #125) — see
    `_regions_constraint`.

    Under `--schrodinger` (issue #143) the `minDigit` domain check and the
    constraint-type whitelist below are both skipped: a real Schrödinger link
    carries `minDigit` on purpose (`_schrodinger_domain` reads it) and is
    full of cosmetic constraint types and disabled duplicates that must be
    ignored, not rejected — only the cell-count check still applies."""
    if not schrodinger and _has_key(puzzle_data, ("minDigit", "maxDigit")):
        msg = "non-classic link: a minDigit/maxDigit domain is a variant"
        raise ValueError(msg)
    cells = puzzle_data.get("cells")
    if not isinstance(cells, list) or len(cells) != CELL_COUNT:
        msg = f"non-classic link: expected {CELL_COUNT} cells"
        raise ValueError(msg)
    if schrodinger:
        return
    constraints = puzzle_data.get("constraints", [])
    if not isinstance(constraints, list):
        return
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        kind = constraint.get("type")
        if kind not in (0, 1):
            msg = f"non-classic link: unknown constraint type {kind!r}"
            raise ValueError(msg)


def _has_key(value: object, keys: tuple[str, ...]) -> bool:
    """True if any of `keys` appears anywhere in the nested JSON `value`."""
    if isinstance(value, dict):
        return any(k in value for k in keys) or any(
            _has_key(v, keys) for v in value.values()
        )
    if isinstance(value, list):
        return any(_has_key(item, keys) for item in value)
    return False
