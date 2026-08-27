"""Synthesize the renban (`type 400`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single two-cell renban line, R1C1 -> R1C2, on a boxed
4x4 board (digits 1..4), mirroring `synthesize_whisper_links.py`'s shape. No
given sits on the line itself (spec #737): each fixture instead gives every
*other* cell of a real, valid 4x4 completion, so ordinary row/column/box
elimination alone forces R1C1 and R1C2 to that completion's own values — the
renban rule is the only thing left to decide whether the forced pair runs
consecutive. `found-renban-4x4`'s completion forces the pair `2, 3` (a run of
two consecutive digits); `broke-renban-4x4`'s forces `1, 4` (a gap of 3) —
unsatisfiable once the renban rule is added, since the pair is already
pinned with no freedom left to close the gap.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import RENBAN_TYPE

_SIZE = 4
_PATH_RC = [(1, 1), (1, 2)]

# A real, valid 4x4 completion forcing R1C1=2, R1C2=3 — a consecutive,
# distinct pair.
_GRID_FOUND: dict[tuple[int, int], int] = {
    (1, 1): 2, (1, 2): 3, (1, 3): 1, (1, 4): 4,
    (2, 1): 1, (2, 2): 4, (2, 3): 2, (2, 4): 3,
    (3, 1): 3, (3, 2): 1, (3, 3): 4, (3, 4): 2,
    (4, 1): 4, (4, 2): 2, (4, 3): 3, (4, 4): 1,
}  # fmt: skip

# A second completion forcing R1C1=1, R1C2=4 — a gap of 3.
_GRID_BROKE: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 4, (1, 3): 2, (1, 4): 3,
    (2, 1): 2, (2, 2): 3, (2, 3): 1, (2, 4): 4,
    (3, 1): 3, (3, 2): 1, (3, 3): 4, (3, 4): 2,
    (4, 1): 4, (4, 2): 2, (4, 3): 3, (4, 4): 1,
}  # fmt: skip


def _link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one renban line R1C1 -> R1C2,
    given every cell of `grid` except the line's own two."""
    path = [row_col_to_index(row, col, _SIZE) for row, col in _PATH_RC]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _PATH_RC),
        constraints=[{"type": RENBAN_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_renban_4x4() -> str:
    """4x4 renban, `found` — the surrounding givens force R1C1=2, R1C2=3: an
    adjacent, distinct pair."""
    return _link(_GRID_FOUND)


def broke_renban_4x4() -> str:
    """4x4 renban, `broke` — the surrounding givens force R1C1=1, R1C2=4: a
    gap of 3; unsatisfiable once the renban rule is added, since the pair is
    already pinned with no freedom left to close the gap."""
    return _link(_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-renban-4x4": found_renban_4x4,
    "broke-renban-4x4": broke_renban_4x4,
}
