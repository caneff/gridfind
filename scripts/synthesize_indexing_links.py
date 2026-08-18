"""Synthesize the 159-indexing corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `main()`.

One `found-`/`broke-` pair per axis (`type 600` row-indexing, `type 601`
column-indexing; gridfind owns this wire type, so the split
is a build-time choice rather than read off a real link). Each `found-*`
fixture pins its one marked cell to its own coordinate — the involution's
self-referential fixed point, `(R,C)=V ⟺ (R,V)=C` (or the row-axis
transpose) collapsing to a tautology when `V == C` — which a valid classic
4x4 completion satisfies for free. Each `broke-*` fixture instead pins the
marked cell to a *different* digit and pins the cell the involution then
demands to a conflicting one — both givens legal under classic sudoku alone,
so the puzzle breaks *because of* indexing, not the givens.

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
from pathlib import Path

from gridfind.cell_geometry import row_col_to_index
from gridfind.layers.regions import box_regions
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import INDEXING_COL_TYPE, INDEXING_ROW_TYPE

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

_SIZE = 4


def _link(
    *,
    wire_type: int,
    marked_cells: tuple[int, ...],
    givens: dict[tuple[int, int], int],
) -> str:
    """A boxed 4x4 SudokuMaker document with one indexing block of `wire_type`
    marking `marked_cells` (raw row-major indices), plus classic `given`
    placements."""
    cells: list[dict[str, object]] = [{} for _ in range(_SIZE * _SIZE)]
    for (row, col), value in givens.items():
        cells[row_col_to_index(row, col, _SIZE)] = {"given": True, "value": value}
    region_numbers = box_regions(_SIZE, 2, 2).to_labels(_SIZE)
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {
            "cells": cells,
            "size": _SIZE,
            "constraints": [
                {"type": 0},
                {"type": 1, "regions": region_numbers},
                {"type": wire_type, "cells": list(marked_cells), "style": {}},
            ],
        },
    }
    return document_to_link(document)


def found_indexing_row_4x4() -> str:
    """`found` — row-indexing (`type 600`) marks R2C1; the given R2C1=2 is the
    involution's fixed point (`(2,C1)=2 ⟺ (2,C1)=2`), trivially satisfied by
    any classic completion."""
    return _link(
        wire_type=INDEXING_ROW_TYPE,
        marked_cells=(row_col_to_index(2, 1, _SIZE),),
        givens={(2, 1): 2},
    )


def broke_indexing_row_4x4() -> str:
    """`broke` — row-indexing marks R2C1=3, which demands `(3,C1)=R3C1` hold
    `R=2`; R3C1 is separately given 4. Both givens are legal under classic
    sudoku alone (different rows, different digits), so the break is the
    indexing involution, not a plain classic collision."""
    return _link(
        wire_type=INDEXING_ROW_TYPE,
        marked_cells=(row_col_to_index(2, 1, _SIZE),),
        givens={(2, 1): 3, (3, 1): 4},
    )


def found_indexing_col_4x4() -> str:
    """`found` — column-indexing (`type 601`) marks R1C2; the given R1C2=2 is
    the involution's fixed point (`(R1,2)=2 ⟺ (R1,2)=2`)."""
    return _link(
        wire_type=INDEXING_COL_TYPE,
        marked_cells=(row_col_to_index(1, 2, _SIZE),),
        givens={(1, 2): 2},
    )


def broke_indexing_col_4x4() -> str:
    """`broke` — column-indexing marks R1C2=3, which demands `(R1,3)=R1C3`
    hold `C=2`; R1C3 is separately given 4. Both givens are legal under
    classic sudoku alone (same row, different digits/columns), so the break
    is the indexing involution, not a plain classic collision."""
    return _link(
        wire_type=INDEXING_COL_TYPE,
        marked_cells=(row_col_to_index(1, 2, _SIZE),),
        givens={(1, 2): 3, (1, 3): 4},
    )


def _scell_link(*, control_value: int, scell_pair: str, r1c2: int, r1c3: int) -> str:
    """A boxed 4x4 document: a column-indexing block (`type 601`) marking
    R1C4, given `control_value`; R1C1 declared an S-cell holding `scell_pair`
    through a `type 2001` `S-cell` marker cage — the cell the control's
    index targets; and R1C2/R1C3 given, filling row 1's two ordinary
    remaining digits so the row's classic `0..4` cover is complete."""
    cells: list[dict[str, object]] = [{} for _ in range(_SIZE * _SIZE)]
    cells[row_col_to_index(1, 4, _SIZE)] = {"given": True, "value": control_value}
    cells[row_col_to_index(1, 2, _SIZE)] = {"given": True, "value": r1c2}
    cells[row_col_to_index(1, 3, _SIZE)] = {"given": True, "value": r1c3}
    region_numbers = box_regions(_SIZE, 2, 2).to_labels(_SIZE)
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {
            "cells": cells,
            "size": _SIZE,
            "constraints": [
                {"type": 0},
                {"type": 1, "regions": region_numbers},
                {
                    "type": INDEXING_COL_TYPE,
                    "cells": [row_col_to_index(1, 4, _SIZE)],
                    "style": {},
                },
                {
                    "name": "S-cell",
                    "type": 2001,
                    "cages": [
                        {"value": scell_pair, "cells": [row_col_to_index(1, 1, _SIZE)]}
                    ],
                },
            ],
        },
    }
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


def main() -> None:
    """Regenerate every indexing corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
