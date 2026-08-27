"""Synthesize the whisper (`type 401`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single two-cell whisper line, R1C1 -> R1C2, on a boxed
4x4 board (digits 1..4) with `minDifference: 3` — the widest gap the domain
allows, so only the two ends of the range (1 and 4) can satisfy it. No given
sits on the line itself: each fixture instead gives every
*other* cell of a real, valid 4x4 completion, so ordinary row/column/box
elimination alone forces R1C1 and R1C2 to that completion's own values — the
whisper rule is the only thing left to decide whether the forced pair clears
the gap. `found-whisper-4x4`'s completion forces the pair `1, 4` (a gap of
exactly 3); `broke-whisper-4x4`'s forces `1, 2` (a gap of 1) — unsatisfiable
once the whisper rule is added, since the pair is already pinned with no
freedom left to widen it.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import WHISPER_TYPE

_SIZE = 4
_MIN_DIFFERENCE = 3
_PATH_RC = [(1, 1), (1, 2)]

# A real, valid 4x4 completion forcing R1C1=1, R1C2=4 — a gap of exactly 3.
_GRID_FOUND: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 4, (1, 3): 2, (1, 4): 3,
    (2, 1): 2, (2, 2): 3, (2, 3): 1, (2, 4): 4,
    (3, 1): 3, (3, 2): 1, (3, 3): 4, (3, 4): 2,
    (4, 1): 4, (4, 2): 2, (4, 3): 3, (4, 4): 1,
}  # fmt: skip

# A second completion forcing R1C1=1, R1C2=2 — a gap of 1.
_GRID_BROKE: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 2, (1, 3): 3, (1, 4): 4,
    (2, 1): 3, (2, 2): 4, (2, 3): 1, (2, 4): 2,
    (3, 1): 2, (3, 2): 1, (3, 3): 4, (3, 4): 3,
    (4, 1): 4, (4, 2): 3, (4, 3): 2, (4, 4): 1,
}  # fmt: skip


def _link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one whisper line R1C1 -> R1C2
    at `minDifference: 3`, given every cell of `grid` except the line's own
    two."""
    path = [row_col_to_index(row, col, _SIZE) for row, col in _PATH_RC]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _PATH_RC),
        constraints=[
            {
                "type": WHISPER_TYPE,
                "lines": [path],
                "minDifference": _MIN_DIFFERENCE,
            }
        ],
    )
    return document_to_link(document)


def found_whisper_4x4() -> str:
    """4x4 whisper (`minDifference: 3`), `found` — the surrounding givens
    force R1C1=1, R1C2=4: a gap of exactly 3."""
    return _link(_GRID_FOUND)


def broke_whisper_4x4() -> str:
    """4x4 whisper (`minDifference: 3`), `broke` — the surrounding givens
    force R1C1=1, R1C2=2: a gap of 1; unsatisfiable once the whisper rule is
    added, since the pair is already pinned with no freedom left to widen
    it."""
    return _link(_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-whisper-4x4": found_whisper_4x4,
    "broke-whisper-4x4": broke_whisper_4x4,
}
