"""Synthesize the region-sum (`type 404`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single four-cell region-sum line along the first row,
R1C1 -> R1C2 -> R1C3 -> R1C4, on a boxed 4x4 board (digits 1..4) tiled 2x2:
R1C1/R1C2 share the top-left box, R1C3/R1C4 the top-right, so the path
crosses exactly one region boundary and cuts into two two-cell segments. All
four cells are given a permutation of 1..4 (`rows-distinct` already forces
one), so each fixture's segment sums are fixed regardless of the rest of the
grid. `found-region-sum-4x4` gives `1 4 2 3` (segment sums 5 and 5, equal);
`broke-region-sum-4x4` gives `1 2 3 4` (segment sums 3 and 7, a direct
contradiction independent of completion).
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import REGION_SUM_TYPE

_SIZE = 4


def _link(row: tuple[int, int, int, int]) -> str:
    """A boxed 4x4 SudokuMaker document with one region-sum line along row 1,
    R1C1 -> R1C2 -> R1C3 -> R1C4, each cell given `row`'s own digit."""
    path = [row_col_to_index(1, col, _SIZE) for col in range(1, 5)]
    givens = {(1, col): digit for col, digit in zip(range(1, 5), row, strict=True)}
    document = boxed_document(
        2,
        2,
        givens=givens,
        constraints=[{"type": REGION_SUM_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_region_sum_4x4() -> str:
    """4x4 region-sum along row 1, given `1 4 2 3` — the top-left box segment
    (R1C1, R1C2) sums to 5, the top-right (R1C3, R1C4) also to 5."""
    return _link((1, 4, 2, 3))


def broke_region_sum_4x4() -> str:
    """4x4 region-sum along row 1, given `1 2 3 4` — the top-left box segment
    sums to 3, the top-right to 7; unsatisfiable no matter how the rest of
    the board is filled, since every path cell is given."""
    return _link((1, 2, 3, 4))


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-region-sum-4x4": found_region_sum_4x4,
    "broke-region-sum-4x4": broke_region_sum_4x4,
}
