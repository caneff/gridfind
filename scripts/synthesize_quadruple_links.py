"""Synthesize the quadruple (`type 303`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue the 2x2 block straddling all four boxes of a boxed 4x4
board (R2C2/R2C3/R3C2/R3C3) rather than a box-aligned block: a box-aligned
2x2 on a 4x4 board always holds every digit (box size equals the domain
size), which would make any digit's presence trivially true and could never
prove `broke`.

Neither fixture gives any of the four straddling cells directly (spec #723
dec 3): each fixture instead gives every *other* cell from a real, valid
completion (verified via a throwaway backtracking solver, then confirmed
against the actual verdict engine), so each straddling cell's box supplies
its missing digit by ordinary box elimination alone. `found-quadruple-4x4`'s
completion lands the required digit (1) on two of the four forced cells;
`broke-quadruple-4x4`'s completion never lands the required digit (4) on any
of the four — a contradiction no matter how the rest of the board is filled.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, grid_from_rows, off_path_givens

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.quadruple import quad_to_corner
from gridfind.sudokumaker.wire_types import QUADRUPLE_TYPE

_SIZE = 4
_CORNER = quad_to_corner(2, 2, _SIZE)
_QUAD_RC = [(2, 2), (2, 3), (3, 2), (3, 3)]

# Full, valid 4x4-box completions with every cell but the straddling block
# given, so the block's own four cells are forced by ordinary box
# elimination alone rather than by a given sitting on the quadruple's own
# cells.
_FOUND_GRID = grid_from_rows(
    [
        [1, 2, 3, 4],
        [3, 4, 1, 2],
        [2, 1, 4, 3],
        [4, 3, 2, 1],
    ]
)
_BROKE_GRID = grid_from_rows(
    [
        [1, 2, 4, 3],
        [4, 3, 1, 2],
        [2, 1, 3, 4],
        [3, 4, 2, 1],
    ]
)


def _link(digits: list[int], grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one quadruple clue over the
    straddling block R2C2/R2C3/R3C2/R3C3, `grid`'s off-block cells given."""
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _QUAD_RC),
        constraints=[
            {
                "type": QUADRUPLE_TYPE,
                "clues": [{"corner": _CORNER, "digits": digits}],
            }
        ],
    )
    return document_to_link(document)


def found_quadruple_4x4() -> str:
    """4x4, `found` — every cell but the straddling block given from a real
    completion that forces R2C3 and R3C2 to the clue's one required digit
    (1) by ordinary box elimination alone: satisfied regardless of which of
    the two forced cells holds it."""
    return _link([1], _FOUND_GRID)


def broke_quadruple_4x4() -> str:
    """4x4, `broke` — every cell but the straddling block given from a real
    completion that forces all four straddling cells to a digit other than
    the required 4 by ordinary box elimination alone: a direct
    contradiction, unsatisfiable no matter how the rest of the board is
    filled."""
    return _link([4], _BROKE_GRID)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-quadruple-4x4": found_quadruple_4x4,
    "broke-quadruple-4x4": broke_quadruple_4x4,
}
