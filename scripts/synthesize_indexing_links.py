"""Synthesize the 159-indexing corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

One `found-`/`broke-` pair per axis (`type 600` row-indexing, `type 601`
column-indexing; gridfind owns this wire type, so the split
is a build-time choice rather than read off a real link). Each pair marks
R1C1, whose placed value names a position on the indexed line — down its
column for row-indexing, across its row for column-indexing. The line's cell
at that position must hold R1C1's own coordinate on the other axis (1). The
`found-*` fixture gives only that target cell the matching 1 and leaves R1C1
empty, so indexing *forces* R1C1=2 and the completion shows the 2 emerging
from the rule rather than being handed it. The `broke-*` fixture writes R1C1=2
and gives the target a conflicting digit, legal under classic sudoku alone, so
the puzzle breaks *because of* indexing. The blocks carry SudokuMaker's own
indexer color so the link renders as the real indexer component, not a plain
black square.

A third `found-`/`broke-` pair proves the S-cell-aware behaviour:
R1C4 marks column-indexing at digit 1, demanding
`(R1,1)=R1C1` hold R1C4's own column (4); R1C1 is declared an S-cell via a
`type 2001` `S-cell` marker cage (the sole decode-time S-cell channel,
ADR-0012), matched through its *second* digit rather than its first — a
control indexing from both digits of its own S-cell pair is provable only
off classic row/column distinctness (any real puzzle's `type 0` always
carries it), since two live index targets in one line would force the same
coordinate digit to repeat in that line; that finer case is the layer
seam's (`indexing_test.py`), not the corpus link's. The `found-*` fixture's
S-cell pair holds the demanded column; the `broke-*` fixture's pair holds
neither of the demanded digits, both legal classic-Schrödinger row
assignments otherwise.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import INDEXING_COL_TYPE, INDEXING_ROW_TYPE

_SIZE = 4

# SudokuMaker's own indexer-component colors (semi-transparent), read off a
# real 600/601 link: red for column-indexing, blue for row-indexing. An empty
# style renders as a plain black square, not the indexer component, so every
# synthesized block carries its axis color.
_INDEXER_COLOR = {INDEXING_ROW_TYPE: "#0080f955", INDEXING_COL_TYPE: "#f9000055"}


def _link(
    *,
    wire_type: int,
    marked_cells: tuple[int, ...],
    givens: dict[tuple[int, int], int],
) -> str:
    """A boxed 4x4 SudokuMaker document with one indexing block of `wire_type`
    marking `marked_cells` (raw row-major indices), plus classic `given`
    placements."""
    document = boxed_document(
        2,
        2,
        givens=givens,
        constraints=[
            {
                "type": wire_type,
                "cells": list(marked_cells),
                "style": {"color": _INDEXER_COLOR[wire_type]},
            }
        ],
    )
    return document_to_link(document)


def found_indexing_row_4x4() -> str:
    """`found` — row-indexing (`type 600`) marks R1C1 with no given value. Only
    the target R2C1=1 is given: in column 1, digit 1 sits at row 2. Row-indexing
    then forces R1C1=2 (value 2 names position 2 down column 1, whose cell holds
    R1C1's row, 1), so the completion *shows* the 2 emerging from the rule rather
    than being handed it."""
    return _link(
        wire_type=INDEXING_ROW_TYPE,
        marked_cells=(row_col_to_index(1, 1, _SIZE),),
        givens={(2, 1): 1},
    )


def broke_indexing_row_4x4() -> str:
    """`broke` — the row-indexing found pair's mismatch: R1C1=2 demands R2C1
    hold 1, but R2C1 is given 3. Both givens are legal under classic sudoku
    alone (different rows, different digits), so the break is the indexing
    involution, not a plain classic collision."""
    return _link(
        wire_type=INDEXING_ROW_TYPE,
        marked_cells=(row_col_to_index(1, 1, _SIZE),),
        givens={(1, 1): 2, (2, 1): 3},
    )


def found_indexing_col_4x4() -> str:
    """`found` — column-indexing (`type 601`) marks R1C1 with no given value.
    Only the target R1C2=1 is given: in row 1, digit 1 sits at column 2.
    Column-indexing then forces R1C1=2 (value 2 names position 2 across row 1,
    whose cell holds R1C1's column, 1), so the completion *shows* the 2 emerging
    from the rule rather than being handed it."""
    return _link(
        wire_type=INDEXING_COL_TYPE,
        marked_cells=(row_col_to_index(1, 1, _SIZE),),
        givens={(1, 2): 1},
    )


def broke_indexing_col_4x4() -> str:
    """`broke` — the column-indexing found pair's mismatch: R1C1=2 demands R1C2
    hold 1, but R1C2 is given 3. Both givens are legal under classic sudoku
    alone (same row, different digits/columns), so the break is the indexing
    involution, not a plain classic collision."""
    return _link(
        wire_type=INDEXING_COL_TYPE,
        marked_cells=(row_col_to_index(1, 1, _SIZE),),
        givens={(1, 1): 2, (1, 2): 3},
    )


def _scell_link(*, control_value: int, scell_pair: str, r1c2: int, r1c3: int) -> str:
    """A boxed 4x4 document: a column-indexing block (`type 601`) marking
    R1C4, given `control_value`; R1C1 declared an S-cell holding `scell_pair`
    through a `type 2001` `S-cell` marker cage — the cell the control's
    index targets; and R1C2/R1C3 given, filling row 1's two ordinary
    remaining digits so the row's classic `0..4` cover is complete."""
    document = boxed_document(
        2,
        2,
        givens={(1, 4): control_value, (1, 2): r1c2, (1, 3): r1c3},
        constraints=[
            {
                "type": INDEXING_COL_TYPE,
                "cells": [row_col_to_index(1, 4, _SIZE)],
                "style": {"color": _INDEXER_COLOR[INDEXING_COL_TYPE]},
            },
            {
                "name": "S-cell",
                "type": 2001,
                "cages": [
                    {"value": scell_pair, "cells": [row_col_to_index(1, 1, _SIZE)]}
                ],
            },
        ],
    )
    return document_to_link(document)


def found_indexing_scell_col_4x4() -> str:
    """`found` — R1C4 marks column-indexing at digit 1: position 1 demands
    `(R1,1)=R1C1` hold `C=4`, R1C4's own column. R1C1 is an S-cell holding
    `{0, 4}`, matched through its *second* digit — proving membership over a
    widened cell, not just its first slot."""
    return _scell_link(control_value=1, scell_pair="0,4", r1c2=2, r1c3=3)


def broke_indexing_scell_col_4x4() -> str:
    """`broke` — the same control digit, but R1C1's S-cell pair is `{0, 3}`
    instead of `{0, 4}`: neither digit matches the demanded column (4), so
    the membership check fails and the puzzle breaks."""
    return _scell_link(control_value=1, scell_pair="0,3", r1c2=2, r1c3=4)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-indexing-row-4x4": found_indexing_row_4x4,
    "broke-indexing-row-4x4": broke_indexing_row_4x4,
    "found-indexing-col-4x4": found_indexing_col_4x4,
    "broke-indexing-col-4x4": broke_indexing_col_4x4,
    "found-indexing-scell-col-4x4": found_indexing_scell_col_4x4,
    "broke-indexing-scell-col-4x4": broke_indexing_scell_col_4x4,
}
