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

The decode is split by responsibility across this package's modules —
`boundary` (document decompress/compress, size/domain, the shared
enabled-block walk), `cells` (per-cell decode), `cages` (killer/cosmetic
cages, thermometers), `markers` (named marker-cage classification, ADR-0012),
`edge_clues` (XV/kropki), `regions` (the `type 1` block), and `registry`
(`DECODER_REGISTRY`) — with `decode_link` itself living here as the one
function that threads all of them together. `decode_link`/`encode_link`
remain the package's public door; every name any importer previously pulled
from the single `sudokumaker.py` module is re-exported below.
"""

from __future__ import annotations

from typing import Any

from gridfind.cell_geometry import cell_geometry
from gridfind.puzzle import (
    Board,
    Constraint,
    Puzzle,
    WorkingState,
)
from gridfind.sudokumaker.boundary import (
    _CLASSIC_SIZE,
    _as_int,
    _board_size,
    _digit_domain,
    _enabled_blocks,
    _schrodinger_domain,
    decode_document,
    encode_link,
)
from gridfind.sudokumaker.cages import (
    _CAGE_TYPE,
    _THERMO_TYPE,
    _cage_constraints,
    _cosmetic_cage_constraints,
    _cosmetic_cage_killer_sum,
    _CosmeticCageDecode,
    _killer_cage,
    _thermo_constraints,
)
from gridfind.sudokumaker.cells import (
    _MAX_SINGLE_DIGIT,
    _SCELL_PIN_DIGITS,
    _address,
    _addresses,
    _CellDecode,
    _decode_cell,
    _parse_digit,
    _scell_directive_from_value,
    _write_s_cell,
    write_cell,
)
from gridfind.sudokumaker.edge_clues import (
    _KROPKI_BLACK_TYPE,
    _KROPKI_WHITE_TYPE,
    _XV_ALIASES,
    _XV_TYPE,
    _black_kropki_constraints,
    _edge_clue_constraints,
    _kropki_constraints,
    _warn_dropped_negative,
    _xv_constraints,
)
from gridfind.sudokumaker.markers import (
    _COSMETIC_CAGE_TYPE,
    _DOUBLER_MARKER_LABELS,
    _MARKER_KIND_PRIORITY,
    _NAMED_KILLER_CAGE_LABELS,
    _SCELL_MARKER_LABELS,
    CosmeticCageKind,
    _has_scell_marker_block,
    _is_scell_block,
    _scell_marker_values,
    colorize_marker_cages,
    cosmetic_cage_kind,
)
from gridfind.sudokumaker.regions import (
    _classic_regions_for,
    _regions_constraints,
    _regions_matrix,
)
from gridfind.sudokumaker.registry import (
    _ANTI_KING_TYPE,
    _ANTI_KNIGHT_TYPE,
    _LIVE_LIST_KEYS,
    _NEGATIVE_DIAGONAL_TYPE,
    _POSITIVE_DIAGONAL_TYPE,
    _TOGGLE_WIRE_TYPES,
    DECODER_REGISTRY,
    DecodedType,
    SetterDoc,
    _global_toggle_handler,
    _warn_on_dropped_constraints,
    constraint_name,
    has_live_data,
)

# The full re-export surface: `decode_link`/`encode_link` are the public
# door, but the package also carries forward every name an existing importer
# (cli, setter_guide, inspect_link, verify_links, and the *_test.py suites)
# previously pulled from the single sudokumaker.py module — including the
# module-private helpers those whitebox tests exercise directly — so every
# import path keeps working unchanged after the split.
__all__ = [
    "DECODER_REGISTRY",
    "_ANTI_KING_TYPE",
    "_ANTI_KNIGHT_TYPE",
    "_CAGE_TYPE",
    "_CLASSIC_SIZE",
    "_COSMETIC_CAGE_TYPE",
    "_DOUBLER_MARKER_LABELS",
    "_KROPKI_BLACK_TYPE",
    "_KROPKI_WHITE_TYPE",
    "_LIVE_LIST_KEYS",
    "_MARKER_KIND_PRIORITY",
    "_MAX_SINGLE_DIGIT",
    "_NAMED_KILLER_CAGE_LABELS",
    "_NEGATIVE_DIAGONAL_TYPE",
    "_POSITIVE_DIAGONAL_TYPE",
    "_SCELL_MARKER_LABELS",
    "_SCELL_PIN_DIGITS",
    "_THERMO_TYPE",
    "_TOGGLE_WIRE_TYPES",
    "_XV_ALIASES",
    "_XV_TYPE",
    "CosmeticCageKind",
    "DecodedType",
    "SetterDoc",
    "_CellDecode",
    "_CosmeticCageDecode",
    "_address",
    "_addresses",
    "_as_int",
    "_black_kropki_constraints",
    "_cage_constraints",
    "_classic_regions_for",
    "_cosmetic_cage_constraints",
    "_cosmetic_cage_killer_sum",
    "_decode_cell",
    "_digit_domain",
    "_edge_clue_constraints",
    "_enabled_blocks",
    "_global_toggle_handler",
    "_has_scell_marker_block",
    "_is_scell_block",
    "_killer_cage",
    "_kropki_constraints",
    "_parse_digit",
    "_regions_constraints",
    "_regions_matrix",
    "_scell_directive_from_value",
    "_scell_marker_values",
    "_schrodinger_domain",
    "_thermo_constraints",
    "_warn_dropped_negative",
    "_warn_on_dropped_constraints",
    "_write_s_cell",
    "_xv_constraints",
    "colorize_marker_cages",
    "constraint_name",
    "cosmetic_cage_kind",
    "decode_document",
    "decode_link",
    "encode_link",
    "has_live_data",
    "write_cell",
]


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
    refusal to strip-and-honor (ADR-0012).

    A `type 2001` block named `Doubler` (case-insensitive, trimmed) marks every
    cell it contains a declared doubler — one `ModifierDirective` per cell, no
    `cage`/`group-sum` for that block — and stands up the `doubler` constraint.
    The marker is orthogonal to the cell's digit: a doubler holds one digit
    worth twice its value, so a given or placement on a marked cell still lands.

    A `type 2001` block named `S-cell`/`Schrödinger` is the analogous S-cell
    marker: each contained cell is a declared S-cell reading its marker cage's
    own `value` for the pair/half/bare directive (ADR-0014) — a comma-split
    `"a,b"` or the two-digit scalar shorthand in a single-digit domain pins the
    pair, one digit is a half S-cell, absent/empty/unparseable is a bare
    S-cell. No `cage`/`group-sum` is emitted for that block. A settled value on
    a marked cell (the cell's own `value`, distinct from the cage's) decodes
    alongside the marker's directive rather than being refused — the two
    collide at solve time (ADR-0014). The marker widens the domain by
    the classic `k = 1` extra digit (`range(minDigit, minDigit + size + 1)`),
    relaxes the classic-only guard, and synthesizes the `schrodinger`
    constraint. Once that layer exists, every cell's settled `given`/bare
    `value` placement — marked or not — decodes to a **singleton pin**
    (`is_s == 0`), not a plain given/placement: the wire's `given` flag does
    not affect the S-cell reading (ADR-0014)."""
    puzzle_data: Any = decode_document(link)["puzzle"]
    size = _board_size(puzzle_data)
    _warn_on_dropped_constraints(puzzle_data)

    cells = puzzle_data["cells"]
    # A named `S-cell`/`Schrödinger` block splits into two signals. Its
    # *presence* enables the mode — widening the domain and synthesizing the
    # `schrodinger` constraint that gives every cell the `is_s` freedom the
    # solver discovers S-cells with — even when the block names no cells
    # (ADR-0014). Its *membership* pins known S-cells: each named address maps
    # to its marker cage's own `value`, the pair/half/bare source (ADR-0014)
    # the S-cell branch of the per-cell decode reads.
    scell_values = _scell_marker_values(puzzle_data, size)
    is_schrodinger = _has_scell_marker_block(puzzle_data)
    domain = (
        _schrodinger_domain(puzzle_data, size)
        if is_schrodinger
        else _digit_domain(puzzle_data, size)
    )
    # `sudokumaker` has no engine, so it builds its own descriptor straight
    # from the board it holds rather than re-deriving the `RxCy` address grid
    # by hand (ADR-0004). `cells` is SudokuMaker's own row-major layout, the
    # same order `geometry.grid` flattens to, so zipping the two walks both
    # in lockstep without either side recomputing the other's indexing.
    board = Board(size=size, values=domain)
    geometry = cell_geometry(board)
    addresses = [address for row in geometry.grid for address in row]
    per_cell: list[_CellDecode] = []
    for cell, address in zip(cells, addresses, strict=True):
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
