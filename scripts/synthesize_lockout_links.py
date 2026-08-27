"""Synthesize the lockout (`type 407`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Both fixtures clue a single three-cell lockout line, R1C1 -> R2C2 -> R3C3, on
a boxed 4x4 board (digits 1..4), where the endpoint threshold is
`4 // 2 = 2` (ADR-0021, amended from a real 4x4 SudokuMaker link). No given
sits on the line itself (spec #737): each fixture instead gives every *other*
cell of a real, valid 4x4 completion, so ordinary row/column/box elimination
alone forces R1C1, R2C2, and R3C3 to that completion's own values — the
lockout rule is the only thing left to decide whether the forced interior
clears the threshold. `found-lockout-4x4`'s completion forces bulbs 1 and 3
(a gap of exactly 2, clearing the threshold with no room to spare) with
interior 4, strictly outside the (1, 3) interval; `broke-lockout-4x4`'s
forces the same bulbs with interior 3, equal to a bulb and so inside the
interval — unsatisfiable once the lockout rule is added, since the three
path values are already pinned with no freedom left to fix it.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import LOCKOUT_TYPE

_SIZE = 4
_PATH_RC = [(1, 1), (2, 2), (3, 3)]

# A real, valid 4x4 completion forcing bulbs 1 and 3 with interior 4 —
# strictly outside the (1, 3) interval.
_GRID_FOUND: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 2, (1, 3): 4, (1, 4): 3,
    (2, 1): 3, (2, 2): 4, (2, 3): 1, (2, 4): 2,
    (3, 1): 2, (3, 2): 1, (3, 3): 3, (3, 4): 4,
    (4, 1): 4, (4, 2): 3, (4, 3): 2, (4, 4): 1,
}  # fmt: skip

# A second completion forcing the same bulbs (1, 3) with interior 3 — equal
# to a bulb, inside the interval.
_GRID_BROKE: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 2, (1, 3): 4, (1, 4): 3,
    (2, 1): 4, (2, 2): 3, (2, 3): 1, (2, 4): 2,
    (3, 1): 2, (3, 2): 1, (3, 3): 3, (3, 4): 4,
    (4, 1): 3, (4, 2): 4, (4, 3): 2, (4, 4): 1,
}  # fmt: skip


def _link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with one lockout line R1C1 ->
    R2C2 -> R3C3, given every cell of `grid` except the line's own three."""
    path = [row_col_to_index(row, col, _SIZE) for row, col in _PATH_RC]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _PATH_RC),
        constraints=[{"type": LOCKOUT_TYPE, "lines": [path]}],
    )
    return document_to_link(document)


def found_lockout_4x4() -> str:
    """4x4 lockout (threshold `4 // 2 = 2`), `found` — the surrounding
    givens force bulbs 1 and 3 (a gap that exactly clears the threshold)
    with interior 4, strictly outside the (1, 3) interval."""
    return _link(_GRID_FOUND)


def broke_lockout_4x4() -> str:
    """4x4 lockout, `broke` — the surrounding givens force the same bulbs
    (1, 3) with interior 3, equal to a bulb and so inside the interval, not
    strictly outside it; unsatisfiable once the lockout rule is added, since
    the three path values are already pinned with no freedom left to fix
    it."""
    return _link(_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-lockout-4x4": found_lockout_4x4,
    "broke-lockout-4x4": broke_lockout_4x4,
}
