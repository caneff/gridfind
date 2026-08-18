"""Synthesize the 159-indexing corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `main()`.

One `found-`/`broke-` pair per axis (`type 600` row-indexing, `type 601`
column-indexing — spec #591/#597; gridfind owns this wire type, so the split
is a build-time choice rather than read off a real link). Each `found-*`
fixture pins its one marked cell to its own coordinate — the involution's
self-referential fixed point, `(R,C)=V ⟺ (R,V)=C` (or the row-axis
transpose) collapsing to a tautology when `V == C` — which a valid classic
4x4 completion satisfies for free. Each `broke-*` fixture instead pins the
marked cell to a *different* digit and pins the cell the involution then
demands to a conflicting one — both givens legal under classic sudoku alone,
so the puzzle breaks *because of* indexing, not the givens.
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


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-indexing-row-4x4": found_indexing_row_4x4,
    "broke-indexing-row-4x4": broke_indexing_row_4x4,
    "found-indexing-col-4x4": found_indexing_col_4x4,
    "broke-indexing-col-4x4": broke_indexing_col_4x4,
}


def main() -> None:
    """Regenerate every indexing corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
