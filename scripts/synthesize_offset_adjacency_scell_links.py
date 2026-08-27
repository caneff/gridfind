"""Synthesize the offset-adjacency-over-an-S-cell corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

`offset_adjacency` (anti-knight, `type 13`) reads each cell's real digit
slots through `Engine.real_digit_values` (ADR-0019 dec 6), so a widened
S-cell contributes both of its digits to the disjointness check, not just its
first slot. This corpus exercises that read composed over a widening
(Schrödinger) layer.

Both fixtures pin R1C1 as an S-cell holding `{1, 2}` and give its knight's-hop
partner R3C2 (down 2, right 1 — the same non-attacking pair
`synthesize_toggle_links.py` uses for the plain-digit anti-knight pair) a
single digit. `found` gives R3C2 the digit 3, disjoint from R1C1's pair, so
anti-knight is satisfied. `broke` gives R3C2 the digit 2 — R1C1's *second*
(gated) digit slot, not its first — so the break can only be shown by a
read that reaches both of R1C1's real digits. Dropping the anti-knight
constraint leaves both variants `found` (verified against the synthesizer,
not asserted here), so anti-knight is the sole cause of the break.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import authored_cage_style, blank_cells, boxed_document, place_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import ANTI_KNIGHT_TYPE

_SIZE = 4
_A = row_col_to_index(1, 1, _SIZE)
_B_ROW_COL = (3, 2)


def _link(*, r3c2: int) -> str:
    """A boxed 4x4 SudokuMaker document: R1C1 pinned as an S-cell holding
    `{1, 2}` via a named `S-cell` marker cage, R3C2 (its knight's-hop
    partner) given `r3c2`, and the anti-knight toggle."""
    cells = blank_cells(_SIZE)
    place_givens(cells, _SIZE, {_B_ROW_COL: r3c2})
    document = boxed_document(
        2,
        2,
        cells=cells,
        constraints=[
            {
                "name": "S-cell",
                "type": 2001,
                "cages": [{"value": "1,2", "cells": [_A]}],
                "style": authored_cage_style(),
            },
            {"type": ANTI_KNIGHT_TYPE},
        ],
    )
    return document_to_link(document)


def found_anti_knight_scell_4x4() -> str:
    """4x4 anti-knight over an S-cell, `found` — R3C2 given 3, disjoint from
    R1C1's pinned digit set `{1, 2}`, so the knight's-hop pair shares no
    digit."""
    return _link(r3c2=3)


def broke_anti_knight_scell_4x4() -> str:
    """4x4 anti-knight over an S-cell, `broke` — R3C2 given 2, R1C1's
    *second* real digit slot, not its first: the break only shows up once
    both of R1C1's digits are read, proving anti-knight reads across both of a
    cell's real digit slots, not its first slot alone."""
    return _link(r3c2=2)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test (`corpus_drift_test.py`) refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-anti-knight-scell-4x4": found_anti_knight_scell_4x4,
    "broke-anti-knight-scell-4x4": broke_anti_knight_scell_4x4,
}
