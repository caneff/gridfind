"""Synthesize the palindrome (`type 402`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `main()`.

Both fixtures clue a single three-cell palindrome line, R1C1 -> R2C2 -> R3C3,
on a boxed 4x4 board (digits 1..4). The mirror pair is the two ends — R1C1
and R3C3, non-attacking (different row, column, and box) so the mirror is the
only rule relating them, mirroring `synthesize_renban_links.py`'s shape.
`found-palindrome-4x4` gives the ends the same digit (a mirrored pair);
`broke-palindrome-4x4` gives them different digits, a direct contradiction
since both are given and no completion can make them equal. The middle cell,
R2C2, is left to the solver — palindrome's rule never touches it.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, regenerate

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import PALINDROME_TYPE

_SIZE = 4


def _link(*, r1c1: int, r3c3: int) -> str:
    """A boxed 4x4 SudokuMaker document with one palindrome line R1C1 ->
    R2C2 -> R3C3, plus the two mirror-pair ends' givens."""
    path = [
        row_col_to_index(1, 1, _SIZE),
        row_col_to_index(2, 2, _SIZE),
        row_col_to_index(3, 3, _SIZE),
    ]
    document = boxed_document(
        2,
        2,
        givens={(1, 1): r1c1, (3, 3): r3c3},
        constraints=[{"type": PALINDROME_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_palindrome_4x4() -> str:
    """4x4 palindrome, `found` — R1C1=1, R3C3=1: a mirrored pair, satisfied
    regardless of the free middle cell or the rest of the board."""
    return _link(r1c1=1, r3c3=1)


def broke_palindrome_4x4() -> str:
    """4x4 palindrome, `broke` — R1C1=1, R3C3=2: an unmirrored pair,
    unsatisfiable no matter how the rest of the board is filled, since both
    ends are given."""
    return _link(r1c1=1, r3c3=2)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-palindrome-4x4": found_palindrome_4x4,
    "broke-palindrome-4x4": broke_palindrome_4x4,
}


def main() -> None:
    """Regenerate every palindrome corpus file from its synthesizer."""
    regenerate(CORPUS)


if __name__ == "__main__":
    main()
