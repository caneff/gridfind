"""Synthesize the sequence (`type 405`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single three-cell sequence line, R1C1 -> R2C2 -> R3C3, on
a boxed 4x4 board (digits 1..4). `found-sequence-4x4` gives the two ends 1 and
3, leaving R2C2 to the solver — an arithmetic progression forces it to 2, the
only value making the successive differences equal. `broke-sequence-4x4`
gives all three cells 1, 2, 4 — differences 1 and 2, unequal, a direct
contradiction since all three cells are given.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import SEQUENCE_TYPE

_SIZE = 4


def _link(*, r1c1: int, r2c2: int | None, r3c3: int) -> str:
    """A boxed 4x4 SudokuMaker document with one sequence line R1C1 ->
    R2C2 -> R3C3, plus R1C1's and R3C3's givens and, when `r2c2` is not
    `None`, the interior cell's."""
    path = [
        row_col_to_index(1, 1, _SIZE),
        row_col_to_index(2, 2, _SIZE),
        row_col_to_index(3, 3, _SIZE),
    ]
    givens = {(1, 1): r1c1, (3, 3): r3c3}
    if r2c2 is not None:
        givens[2, 2] = r2c2
    document = boxed_document(
        2,
        2,
        givens=givens,
        constraints=[{"type": SEQUENCE_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_sequence_4x4() -> str:
    """4x4 sequence (ends 1 and 3), `found` — the interior cell is left to
    the solver, satisfied only by 2 (a common difference of 1)."""
    return _link(r1c1=1, r2c2=None, r3c3=3)


def broke_sequence_4x4() -> str:
    """4x4 sequence (ends 1 and 4), `broke` — the interior cell is given 2,
    making the successive differences 1 and 2, unequal; unsatisfiable no
    matter how the rest of the board is filled, since all three cells are
    given."""
    return _link(r1c1=1, r2c2=2, r3c3=4)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-sequence-4x4": found_sequence_4x4,
    "broke-sequence-4x4": broke_sequence_4x4,
}
