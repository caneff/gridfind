"""Decode a SudokuMaker share link into gridfind's `Puzzle` + `WorkingState`.

One pure function, `decode_link`, mirroring `puzzle.py`'s schema-only role: it
strips the `?puzzle=` payload, lz-string-decompresses it, and maps the
`formatVersion 1.5.0` JSON to the model per the confirmed field-by-field map in
`docs/research/sudoku-link-formats.md` §4a/§4b (issues #54, #172). Size, digit
domain, and regions are read from the link's own fields — `width`/`size` (else
`isqrt(len(cells))`), `minDigit`/`maxDigit` (else `1..N`), and the `type 1`
regions matrix — so any square N decodes (issue #176); a classic 9x9 link takes
the size/domain fallbacks and carries its boxes as an explicit `type 1`, so it
decodes exactly as before. A link gridfind can't answer — non-square, a
cell-count/size mismatch, a domain that doesn't span N, an unknown ruleset — is
rejected with `ValueError` rather than mis-decoded into a confident wrong
verdict.

Regions live *only* in a `type 1` block. A boxed puzzle always ships its boxes
as one (the §4a classic fixture carries it), so its absence means the setter
asked for no regions — a Latin square, rows and columns distinct only, no boxes
invented and no size refused for lacking a box convention. A present matrix
decodes bare when it is the board's box tiling, or rides straight onto the
`regions-distinct` constraint's `params["regions"]` verbatim for a jigsaw
(issue #125), unvalidated — a malformed matrix surfaces as
`MalformedPuzzleError` from `verdict`, never from here.

The `schrodinger`/`reading` keywords (issue #143, spec #139) declare a
SudokuMaker-Schrödinger link explicitly rather than sniffing one: they relax
the `minDigit` guard to read the widened domain, decode each cell's red
`colors` bit and center marks into a Schrödinger working-state directive
(CONTEXT.md `schrodinger` layer). Every link — Schrödinger or not — ignores
the unmodeled constraint types and `disabled` blocks a real link carries,
warning to stderr only when a dropped one carried live data (issue #181).
Without the flag every link decodes exactly as before.

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
import sys
import urllib.parse
from collections.abc import Iterator
from math import isqrt
from typing import Any, cast

from lzstring import LZString

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

# Board size, digit domain, and box partition are all read from the link now
# (issue #176), not from a module constant — a classic 9x9 link, which omits
# every size/domain field, still decodes exactly as before via the fallbacks
# (isqrt -> 9, domain -> 1..9, convention tiling). §4b (issue #172) records the
# omit-when-default wire rule the derivation is written against.

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

# type 202 is XV (decode reference #189): `clues: [{value, edge}], negative:
# [...]`. `value` selects the existing pair-sum alias — 10 is X, 5 is V
# (design #190) — never a raw `sum`, so a puzzle carrying both an XV clue and
# a literal pair-sum on the same cells still hits the alias's own
# fixed-param conflict check in `expand_constraints`.
_XV_TYPE = 202
_XV_ALIASES: dict[int, str] = {10: "x", 5: "v"}

# type 200 is white-kropki (decode reference #191): `clues: [{value, edge}],
# negative: [...]`, the same wire shape as XV. The type number *is* the
# white/black discriminator — 200 is white/difference, 201 black/ratio — so
# `value` is the target difference, honored verbatim onto the existing
# `pair-difference` layer (a labelled non-1 value is never coerced to 1). 201
# is not decoded (no ratio layer, backlog #195); it stays warn-and-dropped.
_KROPKI_WHITE_TYPE = 200

# type 301 is a killer-cage block (design #192): `cages: [{cells, value}]`. The
# `cage` layer is region-only (no-repeats, no sum), so `value` is dropped — 0 is
# SudokuMaker's own no-sum cage (silent), a positive sum is honored as cells-only
# with a loud warning (sum support is backlog #196).
_CAGE_TYPE = 301


def decode_link(
    link: str, *, schrodinger: bool = False, reading: str = _CLASSIC_READING
) -> tuple[Puzzle, WorkingState]:
    """Map a SudokuMaker `?puzzle=` link (or a bare payload) to a square-N
    `Puzzle` + `WorkingState`, sizing the board and domain from the link itself
    (issue #176). Raises `ValueError` on a link gridfind can't answer.

    `schrodinger` **declares** the SudokuMaker-Schrödinger variant (spec #139,
    issue #143) — it is never inferred from the link. It reads the link's
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
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    puzzle_data: Any = json.loads(raw)["puzzle"]
    size = _board_size(puzzle_data)
    _warn_on_dropped_constraints(puzzle_data)
    regions = _regions_constraint(puzzle_data, size)

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

    constraints = [Constraint("rows-distinct"), Constraint("cols-distinct")]
    if regions is not None:
        constraints.append(regions)
    constraints.extend(_xv_constraints(puzzle_data, size))
    constraints.extend(_kropki_constraints(puzzle_data, size))
    constraints.extend(_cage_constraints(puzzle_data, size))
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


def _board_size(puzzle_data: dict[str, object]) -> int:
    """The board's size `N` read from the link, most specific first (§4b): a
    `width` (with `height`, else derived from the cell count), else a `size`,
    else `isqrt(len(cells))` — the classic link, which omits all three, lands
    on `isqrt(81) = 9`. The shape must be square (`rows == cols`) and its cell
    count must match (`rows * cols == len(cells)`); a non-square link or a
    size/count mismatch is refused with its own reason (map #171 targets
    square N only)."""
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
    `digitCount`, per #143's verified wire format) through `minDigit + N`, the
    `k = 1` extra digit the classic Schrödinger rule derives, not reads."""
    min_digit = _as_int(puzzle_data.get("minDigit", 1), "minDigit")
    return range(min_digit, min_digit + size + 1)


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


def _regions_constraint(puzzle_data: dict[str, object], size: int) -> Constraint | None:
    """The `regions-distinct` constraint for an `N`x`N` board, or `None` when
    the link carries no regions at all — a Latin square.

    The region partition lives *only* in a `type 1` block. A boxed SudokuMaker
    puzzle always ships its boxes as an explicit `type 1` matrix (verified: the
    §4a classic fixture carries one), so its absence means the setter asked for
    no regions — rows and columns distinct only, no boxes invented. A present
    matrix decodes bare when it equals the board's box tiling (the engine
    supplies that partition by convention) or rides onto `params["regions"]`
    verbatim for a jigsaw (issue #125, generalized to non-9 in #176). A
    `disabled: true` type-1 block is skipped (issue #143) — a real link may
    carry a disabled duplicate alongside the live one. Never validated here — a
    malformed matrix surfaces from `verdict`, not decode."""
    matrix = _regions_matrix(puzzle_data)
    if matrix is None:
        return None
    if size in BOX_SHAPE and matrix == _classic_regions_for(size):
        return Constraint("regions-distinct")
    return Constraint("regions-distinct", params={"regions": matrix})


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
    order — the shared front the per-type decoders (XV #198, kropki #200, cage
    #199) and `_regions_matrix` all iterate behind. Folds the three guards each
    used to repeat: a non-list `constraints` yields nothing, a non-dict block is
    skipped, and a `disabled` block is skipped (the setter switched it off, so
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
    list (issue #194): gridfind models only the positive clues, so the verdict
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
    cell addresses (design #190), the primitive shared by the XV (#198) and
    white-kropki (#200) decoders.

    Edges are enumerated in row-major blocks of `2 * size`, one block per
    0-indexed row `r0`: within a block, offset `1..size-1` is a horizontal
    (left/right) pair starting `r0`, and offset `size..2*size-1` is a
    vertical (up/down) pair starting `r0` — the two closed-form formulas
    (`edge = 2N*r0 + c0 + 1` horizontal, `edge = 2N*r0 + c0 + N` vertical)
    inverted by `divmod`. Oracle-verified against a real link (#190): X @ 70
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
    """The `type 202` XV clues as aliased pair-sum `Constraint`s (design
    #190): each clue's `value` selects the existing `x`/`v` alias (10/5) and
    its `edge` decodes to the adjacent cell pair via `_edge_to_pair`. A
    `disabled` block is skipped entirely; a non-empty `negative` list is
    warn-and-dropped to stderr (issue #194) while its positive clues still
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
        _warn_dropped_negative(block, "XV")
    return decoded


def _kropki_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 200` white-kropki clues as `pair-difference` `Constraint`s
    (design #191): each clue's `edge` decodes to the adjacent cell pair via
    `_edge_to_pair`, and its `value` is the target difference passed verbatim
    as `diff` — a labelled non-1 dot is honored at that value, never coerced to
    the consecutive default. Only `type 200` (white/difference) decodes here;
    `type 201` (black/ratio) has no ratio layer (backlog #195) and stays on the
    generic warn-and-drop path. A `disabled` block is skipped entirely; a
    non-empty `negative` list is warn-and-dropped to stderr (issue #194) while
    its positive clues still decode."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _KROPKI_WHITE_TYPE):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        for clue in clues:
            a, b = _edge_to_pair(clue["edge"], size)
            params = {"cells": [a, b], "diff": clue["value"]}
            decoded.append(Constraint("pair-difference", params=params))
        _warn_dropped_negative(block, "white-kropki")
    return decoded


def _cage_constraints(puzzle_data: dict[str, object], size: int) -> list[Constraint]:
    """The `type 301` killer cages as region-only `cage` `Constraint`s (design
    #192): each cage's raw `cells` indices map row-major to addresses — the same
    `i // N`, `i % N` scheme givens use — so `[18, 19]` on a 9-board is
    R3C1/R3C2. The `cage` layer reads no sum, so `value` is not passed: a `0`
    (SudokuMaker's no-sum cage) is honored silently, a positive sum decodes
    cells-only and warns to stderr that the sum was dropped (backlog #196). A
    `disabled` block is skipped entirely; an empty `cages` list adds nothing."""
    decoded: list[Constraint] = []
    for block in _enabled_blocks(puzzle_data, _CAGE_TYPE):
        cages = cast("list[dict[str, Any]]", block.get("cages", []))
        for cage in cages:
            cells = [cell_address(i // size + 1, i % size + 1) for i in cage["cells"]]
            decoded.append(Constraint("cage", params={"cells": cells}))
            if cage.get("value", 0) > 0:
                print(
                    "warning: ignoring killer-cage sum — verdict computed without it",
                    file=sys.stderr,
                )
    return decoded


def _warn_on_dropped_constraints(puzzle_data: dict[str, object]) -> None:
    """Ignore every constraint gridfind doesn't model (issue #181), warning to
    stderr for any that carries live data — so a verdict is never silently
    computed under a smaller ruleset than the link states.

    Known types (0 givens / 1 regions / 200 white-kropki / 202 XV / 301
    killer-cage) are modeled elsewhere and pass through. A `disabled` constraint
    is skipped first with no warning: the setter switched it off, so it is not
    part of the puzzle even for a type gridfind knows how to decode. A remaining
    enabled unmodeled constraint is inert (empty or cosmetic-only payload) and
    dropped quietly, or active (a live clue/negative list or a populated group)
    and dropped loudly, named by its `definition.name` when the link carries
    one. Honoring a specific variant rather than dropping it is the opt-in
    variant-decoder path (map #180) — `202` graduated first (issue #198), `301`
    next (issue #199), `200` after (issue #200); each still warns on the part it
    can't model (a kropki/XV `negative` list, a cage's sum), fired from its own
    decoder instead. `201` (black/ratio) is deliberately *not* graduated — no
    ratio layer (backlog #195), so it stays here.

    `has_live_data` is the shared active/inert predicate: this runtime policy
    and `scripts/inspect_link.py`'s `classify_constraint` (issue #182) both
    call it, so the dev tool's report and what the decoder actually drops can
    never disagree (issue #184)."""
    constraints = puzzle_data.get("constraints", [])
    if not isinstance(constraints, list):
        return
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        if constraint.get("disabled") is True:
            continue
        kind = constraint.get("type")
        if kind in (0, 1, _XV_TYPE, _KROPKI_WHITE_TYPE, _CAGE_TYPE):
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
    a rule: a non-empty `clues`/`negative`/`cages` list, or a group holding
    real cells under `input.groups`. Empty payloads and cosmetic-only `lines`
    are inert.

    `cages` is a killer-cage block's (`type 301`) payload. It is decoded now
    (issue #199), so `_warn_on_dropped_constraints` skips it — this entry marks
    a populated cage block `active` for `scripts/inspect_link.py`, exactly as
    the `clues` entry does for decoded XV (`type 202`): a decoded variant still
    carries a live rule the dev tool must not report as inert.

    Public so `scripts/inspect_link.py` classifies constraints against the same
    predicate the decoder drops by (issue #184). `Any` keeps the decoded-JSON
    boundary type (a dict narrowed from the untyped payload), as `decode_link`
    does for `puzzle_data`."""
    for key in ("clues", "negative", "cages"):
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
    from `definition.name` — the field SudokuMaker stores it under (issue
    #182). `None` when the link carries no name for the type. Public alongside
    `has_live_data` for `scripts/inspect_link.py` (issue #184)."""
    definition = constraint.get("definition")
    if isinstance(definition, dict):
        name = definition.get("name")
        if isinstance(name, str):
            return name
    return None
