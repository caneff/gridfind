"""Synthesize the quadruple (`type 303`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `main()`.

Both fixtures clue the 2x2 block straddling all four boxes of a boxed 4x4
board (R2C2/R2C3/R3C2/R3C3) rather than a box-aligned block: a box-aligned
2x2 on a 4x4 board always holds every digit (box size equals the domain
size), which would make any digit's presence trivially true and could never
prove `broke`.

`found-quadruple-4x4` gives R2C2 the clue's one required digit directly —
satisfied regardless of the rest of the board. `broke-quadruple-4x4` gives
all four straddling cells a digit other than the one required — a direct
contradiction, since presence has nowhere left to hold.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, regenerate

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.quadruple import quad_to_corner
from gridfind.sudokumaker.wire_types import QUADRUPLE_TYPE

_SIZE = 4
_CORNER = quad_to_corner(2, 2, _SIZE)


def _link(digits: list[int], givens: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one quadruple clue over the
    straddling block R2C2/R2C3/R3C2/R3C3, plus caller-supplied givens."""
    document = boxed_document(
        2,
        2,
        givens=givens,
        constraints=[
            {
                "type": QUADRUPLE_TYPE,
                "clues": [{"corner": _CORNER, "digits": digits}],
            }
        ],
    )
    return document_to_link(document)


def found_quadruple_4x4() -> str:
    """4x4, `found` — R2C2 given the clue's one required digit (1):
    satisfied regardless of the rest of the board."""
    return _link([1], {(2, 2): 1})


def broke_quadruple_4x4() -> str:
    """4x4, `broke` — all four cells of the clued block given digits other
    than the required 4: a direct contradiction, unsatisfiable no matter how
    the rest of the board is filled."""
    return _link([4], {(2, 2): 1, (2, 3): 2, (3, 2): 3, (3, 3): 1})


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-quadruple-4x4": found_quadruple_4x4,
    "broke-quadruple-4x4": broke_quadruple_4x4,
}


def main() -> None:
    """Regenerate every quadruple corpus file from its synthesizer."""
    regenerate(CORPUS)


if __name__ == "__main__":
    main()
