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
`edge_clues` (XV/kropki), `regions` (the `type 1` block), `registry`
(`DECODER_REGISTRY`), and `decode` (`decode_link` itself, the one function
that threads all of them together). `decode_link`/`encode_link` remain the
package's public door; every name any importer previously pulled from the
single `sudokumaker.py` module is re-exported below.
"""

from __future__ import annotations

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
from gridfind.sudokumaker.decode import decode_link
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
    "_board_size",
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
