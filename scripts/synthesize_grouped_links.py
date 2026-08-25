"""Synthesize the grouped-line (`type 406`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Two groupings prove the one relation covers entropic, modular, and parity
alike (spec #672's acceptance criterion): an entropic (low/mid/high band)
line on a boxed 9x9 board, and a parity (odd/even) line on a boxed 4x4 board
— mirroring `synthesize_palindrome_links.py`'s shape otherwise. Each
grouping's `found` fixture gives its window one digit per band/parity;
`broke` repeats a band/parity within the window, a direct given contradiction
since every windowed cell is given and no completion can re-sort a band.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

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


def _entropic_link(*, r1c1: int, r2c2: int, r3c3: int) -> str:
    """A boxed 9x9 SudokuMaker document with one entropic-grouped line R1C1
    -> R2C2 -> R3C3 (one 3-cell window), plus the window's own givens."""
    size = 9
    path = [
        row_col_to_index(1, 1, size),
        row_col_to_index(2, 2, size),
        row_col_to_index(3, 3, size),
    ]
    document = boxed_document(
        3,
        3,
        givens={(1, 1): r1c1, (2, 2): r2c2, (3, 3): r3c3},
        constraints=[
            {"type": GROUPED_TYPE, "lines": [path], "groups": _ENTROPIC_GROUPS}
        ],
    )
    return document_to_link(document)


def _parity_link(*, r1c1: int, r1c2: int) -> str:
    """A boxed 4x4 SudokuMaker document with one parity-grouped line R1C1 ->
    R1C2 (one 2-cell window), plus the window's own givens."""
    size = 4
    path = [row_col_to_index(1, 1, size), row_col_to_index(1, 2, size)]
    document = boxed_document(
        2,
        2,
        givens={(1, 1): r1c1, (1, 2): r1c2},
        constraints=[{"type": GROUPED_TYPE, "lines": [path], "groups": _PARITY_GROUPS}],
    )
    return document_to_link(document)


def found_grouped_entropic_9x9() -> str:
    """9x9 entropic grouped line, `found` — R1C1=1 (low), R2C2=4 (mid),
    R3C3=7 (high): one digit per band, satisfied regardless of the rest of
    the board."""
    return _entropic_link(r1c1=1, r2c2=4, r3c3=7)


def broke_grouped_entropic_9x9() -> str:
    """9x9 entropic grouped line, `broke` — R1C1=1, R2C2=2: both low-band,
    repeating the window's band, unsatisfiable no matter how the rest of the
    board is filled, since both cells are given."""
    return _entropic_link(r1c1=1, r2c2=2, r3c3=7)


def found_grouped_parity_4x4() -> str:
    """4x4 parity grouped line, `found` — R1C1=1 (odd), R1C2=2 (even): one
    digit per parity, satisfied regardless of the rest of the board."""
    return _parity_link(r1c1=1, r1c2=2)


def broke_grouped_parity_4x4() -> str:
    """4x4 parity grouped line, `broke` — R1C1=1, R1C2=3: both odd,
    repeating the window's parity, unsatisfiable no matter how the rest of
    the board is filled, since both cells are given."""
    return _parity_link(r1c1=1, r1c2=3)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-grouped-entropic-9x9": found_grouped_entropic_9x9,
    "broke-grouped-entropic-9x9": broke_grouped_entropic_9x9,
    "found-grouped-parity-4x4": found_grouped_parity_4x4,
    "broke-grouped-parity-4x4": broke_grouped_parity_4x4,
}
