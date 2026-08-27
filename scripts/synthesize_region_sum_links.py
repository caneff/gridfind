"""Synthesize the region-sum (`type 404`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single four-cell region-sum line along the first row,
R1C1 -> R1C2 -> R1C3 -> R1C4, on a boxed 4x4 board (digits 1..4) tiled 2x2:
R1C1/R1C2 share the top-left box, R1C3/R1C4 the top-right, so the path
crosses exactly one region boundary and cuts into two two-cell segments. No
given sits on the line itself: since the path is the whole of
row 1, each fixture instead gives every cell of rows 2-4 from a real, valid
4x4 completion, so ordinary column/box elimination alone forces row 1 to
that completion's own values — the region-sum rule is the only thing left to
decide whether the forced segment sums match. `found-region-sum-4x4`'s
completion forces row 1 to `1 4 2 3` (segment sums 5 and 5, equal);
`broke-region-sum-4x4`'s forces row 1 to `1 2 3 4` (segment sums 3 and 7) —
unsatisfiable once the region-sum rule is added, since row 1 is already
pinned by the columns below it with no freedom left to fix the mismatch.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import REGION_SUM_TYPE

_SIZE = 4
_PATH_RC = [(1, col) for col in range(1, 5)]

# A real, valid 4x4 completion forcing row 1 to `1 4 2 3` — segment sums 5
# and 5, equal.
_GRID_FOUND: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 4, (1, 3): 2, (1, 4): 3,
    (2, 1): 2, (2, 2): 3, (2, 3): 1, (2, 4): 4,
    (3, 1): 3, (3, 2): 1, (3, 3): 4, (3, 4): 2,
    (4, 1): 4, (4, 2): 2, (4, 3): 3, (4, 4): 1,
}  # fmt: skip

# A second completion forcing row 1 to `1 2 3 4` — segment sums 3 and 7.
_GRID_BROKE: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 2, (1, 3): 3, (1, 4): 4,
    (2, 1): 3, (2, 2): 4, (2, 3): 1, (2, 4): 2,
    (3, 1): 2, (3, 2): 1, (3, 3): 4, (3, 4): 3,
    (4, 1): 4, (4, 2): 3, (4, 3): 2, (4, 4): 1,
}  # fmt: skip


def _link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one region-sum line along row
    1, R1C1 -> R1C2 -> R1C3 -> R1C4, given every cell of `grid` except the
    line's own four (all of row 1)."""
    path = [row_col_to_index(row, col, _SIZE) for row, col in _PATH_RC]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _PATH_RC),
        constraints=[{"type": REGION_SUM_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_region_sum_4x4() -> str:
    """4x4 region-sum along row 1, `found` — the surrounding givens (rows
    2-4) force row 1 to `1 4 2 3`: the top-left box segment (R1C1, R1C2)
    sums to 5, the top-right (R1C3, R1C4) also to 5."""
    return _link(_GRID_FOUND)


def broke_region_sum_4x4() -> str:
    """4x4 region-sum along row 1, `broke` — the surrounding givens force
    row 1 to `1 2 3 4`: the top-left box segment sums to 3, the top-right to
    7; unsatisfiable once the region-sum rule is added, since row 1 is
    already pinned by the columns below it with no freedom left to fix the
    mismatch."""
    return _link(_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-region-sum-4x4": found_region_sum_4x4,
    "broke-region-sum-4x4": broke_region_sum_4x4,
}
