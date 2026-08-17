"""Decode a SudokuMaker share link into gridfind's `Puzzle` + `WorkingState`.

Its core function, `link_to_puzzle`, mirrors `puzzle.py`'s schema-only role: it
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
thermo, cosmetic-cage) — is one row in `DECODER_REGISTRY`: `link_to_puzzle`'s
dispatch, `dropped.warn_on_dropped_constraints`, and `dropped.has_live_data`'s
active/inert check all read that one table instead of each restating "type N
is decoded" by hand.

Declared variants are inferred from named cosmetic cages, never sniffed from a
color or declared out of band. An `S-cell`/`Schrödinger`-named cage relaxes the
`minDigit` guard to read the widened domain, declares its cells S-cells, and
synthesizes the `schrodinger` constraint from marker presence alone (CONTEXT.md
`schrodinger` layer); a `Doubler`-named cage marks its cells modifiers and
stands up the `doubler` constraint the same way. A `Constant <N>`/`Nullifier`-
named cage is the second modifier variant (ADR-0016): it marks its cells
modifiers too, but stands up the `constant` constraint carrying `k` read from
the name itself (`Nullifier` = `Constant 0`) rather than a fixed doubling.
Every link — Schrödinger or not — ignores the unmodeled constraint types and
`disabled` blocks a real link carries, warning to stderr only when a dropped
one carried live data.

Deliberately kept as `ValueError`, not folded into `MalformedPuzzleError`:
every rejection here fires before a `Puzzle` exists at all — it
is this decoder finding a link it does not support, not gridfind finding a
puzzle it cannot answer. A `Puzzle` `link_to_puzzle` does produce is never itself
malformed; a `MalformedPuzzleError` from a *decoded* one would still surface
from `verdict`, same as it would for a hand-built `Puzzle`. Conflating the two
would cost a caller the ability to tell "this share link doesn't decode" from
"this puzzle doesn't hold together" — a distinction worth keeping since only
one of them means the *link* is bad.

One narrow exception (ADR-0016 decisions 3-4): a marker cage carrying a
per-cage `value` field, a link mixing `Doubler` and `Constant` marker cages,
or two `Constant` cages naming different `k`, raise `MalformedPuzzleError`
rather than `ValueError`. These are not "gridfind can't answer this link
shape" — the shape is perfectly readable — they are the link stating
conflicting or misplaced facts about a puzzle-wide value, the same kind of
defect a hand-built `Puzzle` would surface at `verdict`. `Puzzle.__init__`
raising `MalformedPuzzleError` for a malformed `Board` is the existing
precedent for that class firing from inside a constructor step, not only from
`verdict`.

No engine, no `verdict` call. Schema in, model out.

`document_to_link` sits beside `link_to_puzzle` as its inverse: a decoded
document back to an openable link. Two later pieces of work both need it,
so it lands once, on its own.

The decode is split by responsibility across this package's modules —
`boundary` (document decompress/compress, size/domain, the shared
enabled-block walk), `cells` (per-cell decode), `cages` (killer/cosmetic
cages, thermometers), `markers` (named marker-cage classification, ADR-0012),
`global_flags` (the payload-less `Somedoku` component),
`edge_clues` (XV/kropki), `regions` (the `type 1` block), `registry`
(the lean `DECODER_REGISTRY` dispatch table), `dropped` (the drop policy
built on top of it), and `decode` (`link_to_puzzle` itself, the one function
that threads all of them together). `link_to_puzzle`/`document_to_link` are the
package's public door, alongside the rest of the public tool surface listed
in `__all__` below; a module-private (`_`-prefixed) name is imported from its
owning submodule directly.
"""

from __future__ import annotations

from gridfind.sudokumaker.boundary import document_to_link, link_to_document
from gridfind.sudokumaker.cells import write_cell
from gridfind.sudokumaker.decode import link_to_puzzle
from gridfind.sudokumaker.dropped import constraint_name, has_live_data
from gridfind.sudokumaker.markers import (
    CosmeticCageKind,
    colorize_marker_cages,
    cosmetic_cage_kind,
)
from gridfind.sudokumaker.registry import DECODER_REGISTRY

__all__ = [
    "DECODER_REGISTRY",
    "CosmeticCageKind",
    "colorize_marker_cages",
    "constraint_name",
    "cosmetic_cage_kind",
    "document_to_link",
    "has_live_data",
    "link_to_document",
    "link_to_puzzle",
    "write_cell",
]
