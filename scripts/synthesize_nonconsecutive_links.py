"""Synthesize the nonconsecutive (`type 15`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Nonconsecutive is a bare `{type: 15}` toggle (like anti-knight/anti-king), but
unlike those two it has no natural "off-clue" shape of its own to hang a given
directly on — the rule applies to every orthogonal pair on the board, not a
setter-drawn set of cells. So this pair follows the line-family/renban shape
instead (`synthesize_renban_links.py`, spec #723's ruling): a real, valid
completion, given everywhere except one orthogonal pair, R1C1 -> R1C2, so
ordinary row/column/box elimination alone forces that pair to the
completion's own values and the nonconsecutive rule is the only thing left to
decide whether the forced pair holds consecutive digits.

A 4x4 board (2x2 boxes) has **no** nonconsecutive-safe completion at all —
verified by direct CP-SAT search, the same fact `synthesize_toggle_links.py`
already documents for anti-king's own 4x4 box-forced-diagonal-repeat — so,
like `found-anti-king-6x6`, this pair lives on a 6x6 (2x3 boxes) instead.
`found-nonconsecutive-6x6`'s completion is itself nonconsecutive-safe
end to end and forces the tested pair to `1, 5` (four apart);
`broke-nonconsecutive-6x6`'s completion is an ordinary valid sudoku (no
nonconsecutive-safety needed once already broken) that forces the pair to
`1, 2` (one apart, forbidden) — unsatisfiable once the toggle is on, since the
pair is already pinned with no freedom left to separate them.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, grid_from_rows, off_path_givens

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import NONCONSECUTIVE_TYPE

_PAIR_RC = [(1, 1), (1, 2)]

# A real, nonconsecutive-safe 6x6 completion (verified by CP-SAT search: no
# two orthogonal neighbours anywhere in this grid differ by exactly 1)
# forcing R1C1=1, R1C2=5 -- four apart.
_GRID_FOUND = grid_from_rows(
    [
        [1, 5, 3, 6, 4, 2],
        [4, 2, 6, 3, 1, 5],
        [2, 6, 4, 1, 5, 3],
        [5, 3, 1, 4, 2, 6],
        [3, 1, 5, 2, 6, 4],
        [6, 4, 2, 5, 3, 1],
    ]
)

# An ordinary valid 6x6 completion (rows/cols/boxes only -- not itself
# nonconsecutive-safe, which is fine once the tested pair alone breaks it)
# forcing R1C1=1, R1C2=2 -- one apart.
_GRID_BROKE = grid_from_rows(
    [
        [1, 2, 3, 5, 4, 6],
        [4, 6, 5, 2, 1, 3],
        [3, 4, 2, 1, 6, 5],
        [5, 1, 6, 4, 3, 2],
        [2, 3, 1, 6, 5, 4],
        [6, 5, 4, 3, 2, 1],
    ]
)


def _link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 6x6 SudokuMaker document with the nonconsecutive toggle on,
    given every cell of `grid` except the tested orthogonal pair's own two."""
    document = boxed_document(
        2,
        3,
        givens=off_path_givens(grid, _PAIR_RC),
        constraints=[{"type": NONCONSECUTIVE_TYPE}],
    )
    return document_to_link(document)


def found_nonconsecutive_6x6() -> str:
    """6x6 nonconsecutive, `found` -- the surrounding givens force R1C1=1,
    R1C2=5: four apart, and the rest of the completion is itself
    nonconsecutive-safe, so the toggle leaves the whole board solvable."""
    return _link(_GRID_FOUND)


def broke_nonconsecutive_6x6() -> str:
    """6x6 nonconsecutive, `broke` -- the surrounding givens force R1C1=1,
    R1C2=2: one apart; unsatisfiable once the toggle is on, since the pair is
    already pinned with no freedom left to separate them."""
    return _link(_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-nonconsecutive-6x6": found_nonconsecutive_6x6,
    "broke-nonconsecutive-6x6": broke_nonconsecutive_6x6,
}
