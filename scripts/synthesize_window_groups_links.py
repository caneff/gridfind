"""Synthesize the window-groups (`type 16`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Two groupings prove the one rule covers both SudokuMaker presets (spec #754's
acceptance criterion): a low/high split (global entropy's two-group shape) on
a 4x4 board, and the three mod-3 residue classes (global mod) on a 9x9 board.
No given sits on the tested window itself: each fixture instead gives every
*other* cell of a real, valid completion, so ordinary row/column/box
elimination alone forces the window's four cells to that completion's own
values — the window-groups rule is the only thing left to decide whether the
forced window holds a digit from every named group or leaves one out.

Window-groups is a *global* rule — every 2x2 window of the board, not just
the one under test — so a `found` fixture's completion must satisfy it
everywhere, not merely look right at the tested window. `_MOD_GRID_BROKE` is
an ordinary real Sudoku completion (no window-groups rule involved in
building it) whose R4C4/R4C5/R5C4/R5C5 window happens to miss the mod-1
residue class; `_MOD_GRID_FOUND` is instead a genuine CP-SAT witness of
`sudoku` + `window-groups(_MOD_GROUPS)` solved together with no givens at
all — a real completion satisfying the rule at every window, not a hand
construction only checked at one.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, grid_from_rows, off_path_givens

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import GLOBAL_ENTROPY_TYPE


def _mask(*digits: int) -> int:
    mask = 0
    for digit in digits:
        mask |= 1 << digit
    return mask


_LOW_HIGH_GROUPS = [_mask(1, 2), _mask(3, 4)]
_MOD_GROUPS = [_mask(1, 4, 7), _mask(2, 5, 8), _mask(3, 6, 9)]

# The window under test on each board: the four cells left for the solver to
# fill, forced back to the completion's own values by ordinary row/column/box
# elimination alone.
_WINDOW_4X4_RC = [(2, 2), (2, 3), (3, 2), (3, 3)]
_WINDOW_9X9_RC = [(4, 4), (4, 5), (5, 4), (5, 5)]

# A real, valid 4x4 completion. Each 2x2 box's window cell (R2C2, R2C3, R3C2,
# R3C3) is the box's own last missing digit once every other cell is given —
# here that leaves the window holding 4 (high), 1 (low), 1 (low), 4 (high):
# both groups present.
_GRID_4X4_FOUND: dict[tuple[int, int], int] = grid_from_rows([
    [1, 2, 3, 4],
    [3, 4, 1, 2],
    [2, 1, 4, 3],
    [4, 3, 2, 1],
])  # fmt: skip

# A second valid 4x4 completion whose same window forces 1, 2, 2, 1 — every
# cell low, the high group entirely absent.
_GRID_4X4_BROKE: dict[tuple[int, int], int] = grid_from_rows([
    [2, 3, 4, 1],
    [4, 1, 2, 3],
    [3, 2, 1, 4],
    [1, 4, 3, 2],
])  # fmt: skip

# A real, valid 9x9 completion (boxed, classic). Its R4C4/R4C5/R5C4/R5C5
# window forces 3, 6, 2, 9 — residues 0, 0, 2, 0 mod 3: the mod-1 class
# ({1,4,7}) never appears.
_MOD_GRID_BROKE: dict[tuple[int, int], int] = grid_from_rows([
    [1, 2, 3, 4, 5, 6, 7, 8, 9],
    [5, 4, 6, 7, 8, 9, 1, 2, 3],
    [8, 9, 7, 1, 2, 3, 4, 5, 6],
    [2, 1, 4, 3, 6, 5, 8, 9, 7],
    [3, 5, 8, 2, 9, 7, 6, 1, 4],
    [6, 7, 9, 8, 1, 4, 2, 3, 5],
    [4, 3, 1, 5, 7, 2, 9, 6, 8],
    [7, 6, 2, 9, 3, 8, 5, 4, 1],
    [9, 8, 5, 6, 4, 1, 3, 7, 2],
])  # fmt: skip

# A completion satisfying window-groups at *every* 2x2 window of the board,
# not only the tested one — the rule is global, so a `found` fixture needs a
# grid that holds it everywhere, not a grid hand-picked to look right at one
# spot. Found by solving `sudoku` + `window-groups(_MOD_GROUPS)` together
# with no givens at all (`gridfind.verdict.verdict`) and taking the witness —
# an actual CP-SAT solution, not a hand construction. Its R4C4/R4C5/R5C4/R5C5
# window forces 1, 3, 2, 7 — residues 1, 0, 2, 1 mod 3: every class present.
_MOD_GRID_FOUND: dict[tuple[int, int], int] = grid_from_rows([
    [1, 9, 5, 7, 6, 2, 4, 3, 8],
    [3, 2, 4, 9, 8, 1, 6, 5, 7],
    [8, 7, 6, 5, 4, 3, 2, 1, 9],
    [4, 6, 2, 1, 3, 8, 7, 9, 5],
    [5, 1, 9, 2, 7, 6, 8, 4, 3],
    [7, 3, 8, 4, 9, 5, 1, 6, 2],
    [6, 5, 1, 3, 2, 7, 9, 8, 4],
    [2, 4, 3, 8, 1, 9, 5, 7, 6],
    [9, 8, 7, 6, 5, 4, 3, 2, 1],
])  # fmt: skip


def _window_groups_4x4_link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 4x4 SudokuMaker document with a low/high window-groups block,
    given every cell of `grid` except the window's own four."""
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, _WINDOW_4X4_RC),
        constraints=[{"type": GLOBAL_ENTROPY_TYPE, "groups": _LOW_HIGH_GROUPS}],
    )
    return document_to_link(document)


def _window_groups_mod_9x9_link(grid: dict[tuple[int, int], int]) -> str:
    """A boxed 9x9 SudokuMaker document with a mod-3 window-groups block,
    given every cell of `grid` except the window's own four."""
    document = boxed_document(
        3,
        3,
        givens=off_path_givens(grid, _WINDOW_9X9_RC),
        constraints=[{"type": GLOBAL_ENTROPY_TYPE, "groups": _MOD_GROUPS}],
    )
    return document_to_link(document)


def found_window_groups_4x4() -> str:
    """4x4 low/high window-groups, `found` — the surrounding givens force
    the window to 4 (high), 1 (low), 1 (low), 4 (high): both groups present."""
    return _window_groups_4x4_link(_GRID_4X4_FOUND)


def broke_window_groups_4x4() -> str:
    """4x4 low/high window-groups, `broke` — the surrounding givens force the
    window to 1, 2, 2, 1: every cell low, the high group entirely absent."""
    return _window_groups_4x4_link(_GRID_4X4_BROKE)


def found_window_groups_mod_9x9() -> str:
    """9x9 mod-3 window-groups, `found` — the surrounding givens force the
    window to 2, 3, 1, 4: a digit from every residue class present."""
    return _window_groups_mod_9x9_link(_MOD_GRID_FOUND)


def broke_window_groups_mod_9x9() -> str:
    """9x9 mod-3 window-groups, `broke` — the surrounding givens force the
    window to 3, 6, 2, 9: the mod-1 class ({1,4,7}) never appears."""
    return _window_groups_mod_9x9_link(_MOD_GRID_BROKE)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-window-groups-4x4": found_window_groups_4x4,
    "broke-window-groups-4x4": broke_window_groups_4x4,
    "found-window-groups-mod-9x9": found_window_groups_mod_9x9,
    "broke-window-groups-mod-9x9": broke_window_groups_mod_9x9,
}
