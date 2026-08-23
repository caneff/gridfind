"""Synthesize the renban (`type 400`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `main()`.

Both fixtures clue a single two-cell renban line, R1C1 -> R1C2, on a boxed
4x4 board (digits 1..4), mirroring `synthesize_whisper_links.py`'s shape.
`found-renban-4x4` gives the adjacent pair `2, 3` (a run of two consecutive
digits); `broke-renban-4x4` gives `1, 4` (a gap of 3), a direct contradiction
since both cells are given and no completion can close the gap.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, regenerate

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import RENBAN_TYPE

_SIZE = 4


def _link(*, r1c1: int, r1c2: int) -> str:
    """A boxed 4x4 SudokuMaker document with one renban line R1C1 -> R1C2,
    plus the two cells' givens."""
    path = [row_col_to_index(1, 1, _SIZE), row_col_to_index(1, 2, _SIZE)]
    document = boxed_document(
        2,
        2,
        givens={(1, 1): r1c1, (1, 2): r1c2},
        constraints=[{"type": RENBAN_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_renban_4x4() -> str:
    """4x4 renban, `found` — R1C1=2, R1C2=3: an adjacent, distinct pair,
    satisfied regardless of the rest of the board."""
    return _link(r1c1=2, r1c2=3)


def broke_renban_4x4() -> str:
    """4x4 renban, `broke` — R1C1=1, R1C2=4: a gap of 3, unsatisfiable no
    matter how the rest of the board is filled, since both cells are given."""
    return _link(r1c1=1, r1c2=4)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-renban-4x4": found_renban_4x4,
    "broke-renban-4x4": broke_renban_4x4,
}


def main() -> None:
    """Regenerate every renban corpus file from its synthesizer."""
    regenerate(CORPUS)


if __name__ == "__main__":
    main()
