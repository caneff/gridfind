"""Synthesize the sequence (`type 405`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single three-cell sequence line, R1C1 -> R2C2 -> R3C3, on
a boxed 4x4 board (digits 1..4). No given sits on the line itself (spec #723,
ruling #728): each fixture instead gives every *other* cell of a real, valid
4x4 completion, so ordinary row/column/box elimination alone forces the three
path cells to that completion's own values — the sequence rule is the only
thing left to decide whether the forced triple is an arithmetic progression.
`found-sequence-4x4`'s completion forces `1, 2, 3` (a common difference of
1); `broke-sequence-4x4`'s forces `1, 2, 4` (differences 1 and 2, unequal) —
unsatisfiable once the sequence rule is added, since the triple is already
pinned with no freedom left.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import SEQUENCE_TYPE

_SIZE = 4
_PATH_RC = [(1, 1), (2, 2), (3, 3)]

# A real, valid 4x4 completion forcing the diagonal R1C1, R2C2, R3C3 = 1, 2, 3.
_GRID_FOUND: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 3, (1, 3): 2, (1, 4): 4,
    (2, 1): 4, (2, 2): 2, (2, 3): 1, (2, 4): 3,
    (3, 1): 2, (3, 2): 4, (3, 3): 3, (3, 4): 1,
    (4, 1): 3, (4, 2): 1, (4, 3): 4, (4, 4): 2,
}  # fmt: skip

# A second completion forcing the diagonal to 1, 2, 4 — not a progression.
_GRID_BROKE: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 3, (1, 3): 2, (1, 4): 4,
    (2, 1): 4, (2, 2): 2, (2, 3): 1, (2, 4): 3,
    (3, 1): 3, (3, 2): 1, (3, 3): 4, (3, 4): 2,
    (4, 1): 2, (4, 2): 4, (4, 3): 3, (4, 4): 1,
}  # fmt: skip


def _link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one sequence line R1C1 ->
    R2C2 -> R3C3, given every cell of `grid` except the line's own three."""
    path = [row_col_to_index(row, col, _SIZE) for row, col in _PATH_RC]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _PATH_RC),
        constraints=[{"type": SEQUENCE_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_sequence_4x4() -> str:
    """4x4 sequence, `found` — the off-line givens force the diagonal to
    1, 2, 3, an arithmetic progression."""
    return _link(_GRID_FOUND)


def broke_sequence_4x4() -> str:
    """4x4 sequence, `broke` — the off-line givens force the diagonal to
    1, 2, 4, whose differences 1 and 2 are unequal."""
    return _link(_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-sequence-4x4": found_sequence_4x4,
    "broke-sequence-4x4": broke_sequence_4x4,
}
