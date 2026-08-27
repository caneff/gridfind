"""Synthesize the palindrome (`type 402`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single three-cell palindrome line, R1C1 -> R2C2 -> R3C3,
on a boxed 4x4 board (digits 1..4). The mirror pair is the two ends — R1C1
and R3C3, non-attacking (different row, column, and box) so the mirror is the
only rule relating them, mirroring `synthesize_renban_links.py`'s shape. No
given sits on the line itself (spec #737): each fixture instead gives every
*other* cell of a real, valid 4x4 completion, so ordinary row/column/box
elimination alone forces all three path cells to that completion's own
values — the palindrome rule is the only thing left to decide whether the
forced ends match. Palindrome's rule never reads the middle cell, so its
forced value plays no part in the verdict either way. `found-palindrome-4x4`'s
completion forces both ends to 1, a mirrored pair; `broke-palindrome-4x4`'s
forces the ends to 1 and 2, an unmirrored pair — unsatisfiable once the
palindrome rule is added, since the ends are already pinned with no freedom
left to make them match.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import PALINDROME_TYPE

_SIZE = 4
_PATH_RC = [(1, 1), (2, 2), (3, 3)]

# A real, valid 4x4 completion forcing both ends (R1C1, R3C3) to 1 — a
# mirrored pair.
_GRID_FOUND: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 3, (1, 3): 2, (1, 4): 4,
    (2, 1): 4, (2, 2): 2, (2, 3): 3, (2, 4): 1,
    (3, 1): 2, (3, 2): 4, (3, 3): 1, (3, 4): 3,
    (4, 1): 3, (4, 2): 1, (4, 3): 4, (4, 4): 2,
}  # fmt: skip

# A second completion forcing the ends to 1 and 2 — an unmirrored pair.
_GRID_BROKE: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 2, (1, 3): 3, (1, 4): 4,
    (2, 1): 4, (2, 2): 3, (2, 3): 1, (2, 4): 2,
    (3, 1): 3, (3, 2): 4, (3, 3): 2, (3, 4): 1,
    (4, 1): 2, (4, 2): 1, (4, 3): 4, (4, 4): 3,
}  # fmt: skip


def _link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one palindrome line R1C1 ->
    R2C2 -> R3C3, given every cell of `grid` except the line's own three."""
    path = [row_col_to_index(row, col, _SIZE) for row, col in _PATH_RC]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _PATH_RC),
        constraints=[{"type": PALINDROME_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_palindrome_4x4() -> str:
    """4x4 palindrome, `found` — the surrounding givens force both ends to
    1, a mirrored pair."""
    return _link(_GRID_FOUND)


def broke_palindrome_4x4() -> str:
    """4x4 palindrome, `broke` — the surrounding givens force the ends to 1
    and 2, an unmirrored pair; unsatisfiable once the palindrome rule is
    added, since the ends are already pinned with no freedom left to make
    them match."""
    return _link(_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-palindrome-4x4": found_palindrome_4x4,
    "broke-palindrome-4x4": broke_palindrome_4x4,
}
