"""Synthesize the between (`type 403`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single three-cell between line, R1C1 -> R2C2 -> R3C3, on
a boxed 4x4 board (digits 1..4). R1C1 and R3C3 are the bulbs, given 1 and 4 —
the widest interval the domain allows, so the interior cell must land on 2 or
3. `found-between-4x4` leaves R2C2 to the solver, satisfied by either;
`broke-between-4x4` gives R2C2 equal to a bulb (1), which is not strictly
between, a direct contradiction since all three cells are given.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import BETWEEN_TYPE

_SIZE = 4


def _link(*, r1c1: int, r3c3: int, r2c2: int | None) -> str:
    """A boxed 4x4 SudokuMaker document with one between line R1C1 ->
    R2C2 -> R3C3, plus the two bulbs' givens and, when `r2c2` is not `None`,
    the interior cell's."""
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
        constraints=[{"type": BETWEEN_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_between_4x4() -> str:
    """4x4 between (bulbs 1 and 4), `found` — the interior cell is left to
    the solver, satisfied by either 2 or 3."""
    return _link(r1c1=1, r3c3=4, r2c2=None)


def broke_between_4x4() -> str:
    """4x4 between (bulbs 1 and 4), `broke` — the interior cell is given 1,
    equal to a bulb and so not strictly between; unsatisfiable no matter how
    the rest of the board is filled, since all three cells are given."""
    return _link(r1c1=1, r3c3=4, r2c2=1)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-between-4x4": found_between_4x4,
    "broke-between-4x4": broke_between_4x4,
}
