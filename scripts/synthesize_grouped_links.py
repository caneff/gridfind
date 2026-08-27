"""Synthesize the grouped-line (`type 406`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Two groupings prove the one relation covers entropic, modular, and parity
alike (spec #672's acceptance criterion): an entropic (low/mid/high band)
line on a boxed 9x9 board, and a parity (odd/even) line on a boxed 4x4 board
— mirroring `synthesize_palindrome_links.py`'s shape otherwise. No given
sits on either line itself: each fixture instead gives every
*other* cell of a real, valid completion, so ordinary row/column/box
elimination alone forces the window's cells to that completion's own values
— the grouped rule is the only thing left to decide whether the forced
window holds one digit per band/parity or repeats one. Each `found` fixture's
completion forces one digit per band/parity in the window; each `broke`
fixture's forces a repeat — unsatisfiable once the grouped rule is added,
since the window is already pinned with no freedom left to re-sort it.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, grid_from_rows, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import GROUPED_TYPE


def _mask(*digits: int) -> int:
    mask = 0
    for digit in digits:
        mask |= 1 << digit
    return mask


_ENTROPIC_GROUPS = [_mask(1, 2, 3), _mask(4, 5, 6), _mask(7, 8, 9)]
_PARITY_GROUPS = [_mask(1, 3), _mask(2, 4)]

_ENTROPIC_PATH_RC = [(1, 1), (2, 2), (3, 3)]
_PARITY_PATH_RC = [(1, 1), (1, 2)]

# A real, valid 9x9 completion forcing R1C1=1 (low), R2C2=4 (mid), R3C3=7
# (high) — one digit per band.
_ENTROPIC_GRID_FOUND: dict[tuple[int, int], int] = grid_from_rows([
    [1, 2, 3, 4, 5, 6, 7, 8, 9],
    [5, 4, 6, 7, 8, 9, 1, 2, 3],
    [8, 9, 7, 1, 2, 3, 4, 5, 6],
    [2, 1, 4, 3, 6, 5, 8, 9, 7],
    [3, 5, 8, 2, 9, 7, 6, 1, 4],
    [6, 7, 9, 8, 1, 4, 2, 3, 5],
    [4, 3, 1, 5, 7, 2, 9, 6, 8],
    [7, 6, 2, 9, 3, 8, 5, 4, 1],
    [9, 8, 5, 6, 4, 1, 3, 7, 2],
])  # fmt: skip

# A second 9x9 completion forcing R1C1=1, R2C2=2 (both low) with R3C3=7 —
# the window repeats the low band.
_ENTROPIC_GRID_BROKE: dict[tuple[int, int], int] = grid_from_rows([
    [1, 3, 4, 2, 5, 6, 7, 8, 9],
    [5, 2, 6, 7, 8, 9, 1, 3, 4],
    [8, 9, 7, 1, 3, 4, 2, 5, 6],
    [2, 1, 3, 4, 6, 5, 8, 9, 7],
    [4, 5, 8, 3, 9, 7, 6, 1, 2],
    [6, 7, 9, 8, 1, 2, 3, 4, 5],
    [3, 4, 2, 5, 7, 1, 9, 6, 8],
    [7, 6, 1, 9, 4, 8, 5, 2, 3],
    [9, 8, 5, 6, 2, 3, 4, 7, 1],
])  # fmt: skip

# A real, valid 4x4 completion forcing R1C1=1 (odd), R1C2=2 (even) — one
# digit per parity.
_PARITY_GRID_FOUND: dict[tuple[int, int], int] = grid_from_rows([
    [1, 2, 3, 4],
    [3, 4, 1, 2],
    [2, 1, 4, 3],
    [4, 3, 2, 1],
])  # fmt: skip

# A second 4x4 completion forcing R1C1=1, R1C2=3 — both odd, the window
# repeats a parity.
_PARITY_GRID_BROKE: dict[tuple[int, int], int] = grid_from_rows([
    [1, 3, 2, 4],
    [2, 4, 1, 3],
    [3, 1, 4, 2],
    [4, 2, 3, 1],
])  # fmt: skip


def _entropic_link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 9x9 SudokuMaker document with one entropic-grouped line R1C1
    -> R2C2 -> R3C3 (one 3-cell window), given every cell of `grid` except
    the window's own three."""
    size = 9
    path = [row_col_to_index(row, col, size) for row, col in _ENTROPIC_PATH_RC]
    document = boxed_document(
        3,
        3,
        givens=off_path_givens(grid, _ENTROPIC_PATH_RC),
        constraints=[
            {"type": GROUPED_TYPE, "lines": [path], "groups": _ENTROPIC_GROUPS}
        ],
    )
    return document_to_link(document)


def _parity_link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one parity-grouped line R1C1 ->
    R1C2 (one 2-cell window), given every cell of `grid` except the
    window's own two."""
    size = 4
    path = [row_col_to_index(row, col, size) for row, col in _PARITY_PATH_RC]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _PARITY_PATH_RC),
        constraints=[{"type": GROUPED_TYPE, "lines": [path], "groups": _PARITY_GROUPS}],
    )
    return document_to_link(document)


def found_grouped_entropic_9x9() -> str:
    """9x9 entropic grouped line, `found` — the surrounding givens force
    R1C1=1 (low), R2C2=4 (mid), R3C3=7 (high): one digit per band."""
    return _entropic_link(_ENTROPIC_GRID_FOUND)


def broke_grouped_entropic_9x9() -> str:
    """9x9 entropic grouped line, `broke` — the surrounding givens force
    R1C1=1, R2C2=2 (both low-band) with R3C3=7; unsatisfiable once the
    grouped rule is added, since the window is already pinned with no
    freedom left to re-sort the repeated band."""
    return _entropic_link(_ENTROPIC_GRID_BROKE)


def found_grouped_parity_4x4() -> str:
    """4x4 parity grouped line, `found` — the surrounding givens force
    R1C1=1 (odd), R1C2=2 (even): one digit per parity."""
    return _parity_link(_PARITY_GRID_FOUND)


def broke_grouped_parity_4x4() -> str:
    """4x4 parity grouped line, `broke` — the surrounding givens force
    R1C1=1, R1C2=3 (both odd); unsatisfiable once the grouped rule is added,
    since the window is already pinned with no freedom left to re-sort the
    repeated parity."""
    return _parity_link(_PARITY_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-grouped-entropic-9x9": found_grouped_entropic_9x9,
    "broke-grouped-entropic-9x9": broke_grouped_entropic_9x9,
    "found-grouped-parity-4x4": found_grouped_parity_4x4,
    "broke-grouped-parity-4x4": broke_grouped_parity_4x4,
}
