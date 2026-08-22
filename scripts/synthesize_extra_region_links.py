"""Synthesize the extra-region (windoku) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `main()`.

One `found-`/`broke-` pair, both over the same windoku-style offset block:
the 2x2 straddling all four boxes of a boxed 4x4 board (`R2C2`, `R2C3`,
`R3C2`, `R3C3`). Only its two diagonal pairs (`R2C2`/`R3C3`, `R2C3`/`R3C2`)
sit in different rows, columns, *and* boxes, so rows/cols/boxes alone never
forbid them repeating — the clean seam a found/broke pair proves the extra
region's own all-different rule adds. The `found-*` fixture gives the
diagonal pair two different digits, already legal everywhere; the `broke-*`
fixture repeats one digit across that same pair, still legal under classic
sudoku alone, so the break is the extra region, not a plain classic
collision.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, regenerate

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import EXTRA_REGION_TYPE

_SIZE = 4

# The windoku-style offset block straddling all four boxes of a boxed 4x4
# board.
_WINDOW = ((2, 2), (2, 3), (3, 2), (3, 3))


def _link(givens: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one extra-region block over
    `_WINDOW`, plus classic `given` placements."""
    document = boxed_document(
        2,
        2,
        givens=givens,
        constraints=[
            {
                "type": EXTRA_REGION_TYPE,
                "cells": [row_col_to_index(row, col, _SIZE) for row, col in _WINDOW],
            }
        ],
    )
    return document_to_link(document)


def found_extra_region_4x4() -> str:
    """`found` — R2C2=1 and R3C3=2 sit diagonally opposite in the extra
    region, already distinct: rows/cols/boxes alone don't forbid the pair
    (different row, column, and box), so a completion exists once the extra
    region's own distinctness is honored too."""
    return _link({(2, 2): 1, (3, 3): 2})


def broke_extra_region_4x4() -> str:
    """`broke` — the found pair's mismatch: R2C2=1 and R3C3=1 repeat inside
    the extra region. Both givens are legal under classic sudoku alone
    (different row, column, and box), so the break is the extra region's own
    all-different rule, not a plain classic collision."""
    return _link({(2, 2): 1, (3, 3): 1})


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-extra-region-4x4": found_extra_region_4x4,
    "broke-extra-region-4x4": broke_extra_region_4x4,
}


def main() -> None:
    """Regenerate every extra-region corpus file from its synthesizer."""
    regenerate(CORPUS)


if __name__ == "__main__":
    main()
