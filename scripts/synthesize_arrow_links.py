"""Synthesize the arrow (`type 408`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

`found-arrow-4x4`/`broke-arrow-4x4` clue one bulb (R1C1) and its one
two-cell shaft (R1C2, R1C3), on a boxed 4x4 board (digits 1..4). No given
sits on the bulb or shaft: each fixture instead gives every *other* cell of
a real, valid 4x4 completion, so ordinary row/column/box elimination alone
forces the bulb and shaft to that completion's own values — the arrow rule
is the only thing left to decide whether the forced shaft sums to the
forced bulb. `found-arrow-4x4`'s completion forces the bulb to 4 and the
shaft to 1 + 3 = 4; `broke-arrow-4x4`'s forces the same bulb (4) but a shaft
of 2 + 1 = 3.

`found-arrow-two-shafts-4x4` clues one bulb (R4C1) with two independent
shafts — a one-cell shaft (R1C4) and a two-cell shaft (R2C4, R3C1) — on a
second valid 4x4 completion that forces the bulb to 4, the one-cell shaft to
4, and the two-cell shaft to 2 + 2 = 4: both shafts hold on their own,
proving the "each shaft independently" rule rather than one combined total.

`found-pill-arrow-6x6`/`broke-pill-arrow-6x6` clue a two-cell pill bulb
(R2C4, R2C5) and its three-cell shaft (R1C1, R4C2, R6C3), on a boxed 6x6
board (digits 1..6, 2x3 boxes — the extra room over 4x4 lets the pill and
shaft cells sit one-per-column, each forced by its own column's single
missing digit rather than needing row/box backtracking). Same off-clue-given
technique as the 4x4 pair. `found`'s completion forces the pill to R2C4=1,
R2C5=2 — a place value of 12, a value in the teens — and the shaft to
1 + 6 + 5 = 12. `broke` swaps in a second valid completion (its row bands 2
and 3 exchanged, so the pill's own row is untouched and still reads 12) that
forces the same shaft cells to 1 + 4 + 4 = 9, unequal.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, grid_from_rows, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import ARROW_TYPE

_SIZE = 4

# found-arrow-4x4 / broke-arrow-4x4: one bulb, one two-cell shaft, all in row 1.
_BULB_RC = (1, 1)
_SHAFT_RC = [(1, 2), (1, 3)]

# A real, valid 4x4 completion forcing the bulb to 4 and the shaft to 1 + 3 = 4.
_GRID_FOUND: dict[tuple[int, int], int] = {
    (1, 1): 4, (1, 2): 1, (1, 3): 3, (1, 4): 2,
    (2, 1): 3, (2, 2): 2, (2, 3): 4, (2, 4): 1,
    (3, 1): 1, (3, 2): 4, (3, 3): 2, (3, 4): 3,
    (4, 1): 2, (4, 2): 3, (4, 3): 1, (4, 4): 4,
}  # fmt: skip

# A second completion forcing the same bulb (4) but a shaft of 2 + 1 = 3.
_GRID_BROKE: dict[tuple[int, int], int] = {
    (1, 1): 4, (1, 2): 2, (1, 3): 1, (1, 4): 3,
    (2, 1): 1, (2, 2): 3, (2, 3): 4, (2, 4): 2,
    (3, 1): 2, (3, 2): 1, (3, 3): 3, (3, 4): 4,
    (4, 1): 3, (4, 2): 4, (4, 3): 2, (4, 4): 1,
}  # fmt: skip

# found-arrow-two-shafts-4x4: one bulb, two independent shafts.
_TWO_SHAFT_BULB_RC = (4, 1)
_TWO_SHAFT_FIRST_RC = [(1, 4)]
_TWO_SHAFT_SECOND_RC = [(2, 4), (3, 1)]

# A valid 4x4 completion forcing the bulb to 4, the one-cell shaft to 4, and
# the two-cell shaft to 2 + 2 = 4 — both shafts hold on their own.
_GRID_TWO_SHAFTS: dict[tuple[int, int], int] = {
    (1, 1): 1, (1, 2): 2, (1, 3): 3, (1, 4): 4,
    (2, 1): 3, (2, 2): 4, (2, 3): 1, (2, 4): 2,
    (3, 1): 2, (3, 2): 1, (3, 3): 4, (3, 4): 3,
    (4, 1): 4, (4, 2): 3, (4, 3): 2, (4, 4): 1,
}  # fmt: skip


def _link(
    grid: dict[tuple[int, int], int],
    bulb_cells_rc: list[tuple[int, int]],
    shafts_rc: list[list[tuple[int, int]]],
    *,
    box_h: int = 2,
    box_w: int = 2,
) -> str:
    """A boxed `box_h`x`box_w` SudokuMaker document with one arrow —
    `bulb_cells_rc` (one cell, or two-or-more for a pill) and one or more
    `shafts_rc` paths — given every cell of `grid` except the clue's own
    bulb and shaft cells."""
    size = box_h * box_w
    clue_cells = [*bulb_cells_rc, *(cell for shaft in shafts_rc for cell in shaft)]
    bulb_indices = [row_col_to_index(*cell, size) for cell in bulb_cells_rc]
    shaft_indices = [
        [row_col_to_index(*cell, size) for cell in shaft] for shaft in shafts_rc
    ]
    document = boxed_document(
        box_h,
        box_w,
        givens=off_path_givens(grid, clue_cells),
        constraints=[
            {
                "type": ARROW_TYPE,
                "bulbsWithArrows": [
                    {"bulbCells": bulb_indices, "arrows": shaft_indices}
                ],
            }
        ],
    )
    return document_to_link(document)


def found_arrow_4x4() -> str:
    """4x4 arrow, `found` — the off-clue givens force the bulb to 4 and the
    shaft to 1 + 3 = 4."""
    return _link(_GRID_FOUND, [_BULB_RC], [_SHAFT_RC])


def broke_arrow_4x4() -> str:
    """4x4 arrow, `broke` — the off-clue givens force the same bulb (4) but
    a shaft of 2 + 1 = 3."""
    return _link(_GRID_BROKE, [_BULB_RC], [_SHAFT_RC])


def found_arrow_two_shafts_4x4() -> str:
    """4x4 arrow with two shafts on one bulb, `found` — the off-clue givens
    force the bulb to 4, the one-cell shaft to 4, and the two-cell shaft to
    2 + 2 = 4: both shafts hold independently."""
    return _link(
        _GRID_TWO_SHAFTS,
        [_TWO_SHAFT_BULB_RC],
        [_TWO_SHAFT_FIRST_RC, _TWO_SHAFT_SECOND_RC],
    )


# found-pill-arrow-6x6 / broke-pill-arrow-6x6: a two-cell pill bulb (R2C4,
# R2C5) and its three-cell shaft (R1C1, R4C2, R6C3), on a 2x3-boxed 6x6
# board. Each clue cell sits alone in its own column, so it's forced by that
# column's single missing digit regardless of the other clue cells sharing a
# row or box.
_PILL_BULB_RC = [(2, 4), (2, 5)]
_PILL_SHAFT_RC = [(1, 1), (4, 2), (6, 3)]

# A valid 6x6 completion forcing the pill to R2C4=1, R2C5=2 (place value
# 12) and the shaft to 1 + 6 + 5 = 12.
_PILL_GRID_FOUND = grid_from_rows(
    [
        [1, 2, 3, 4, 5, 6],
        [4, 5, 6, 1, 2, 3],
        [2, 3, 1, 5, 6, 4],
        [5, 6, 4, 2, 3, 1],
        [3, 1, 2, 6, 4, 5],
        [6, 4, 5, 3, 1, 2],
    ]
)

# A second valid completion — row bands (3,4) and (5,6) swapped, leaving the
# pill's own row (row 2) untouched, so the pill still reads 12 — forcing the
# same shaft cells to 1 + 4 + 4 = 9, unequal to the bulb.
_PILL_GRID_BROKE = grid_from_rows(
    [
        [1, 2, 3, 4, 5, 6],
        [4, 5, 6, 1, 2, 3],
        [3, 1, 2, 6, 4, 5],
        [6, 4, 5, 3, 1, 2],
        [2, 3, 1, 5, 6, 4],
        [5, 6, 4, 2, 3, 1],
    ]
)


def found_pill_arrow_6x6() -> str:
    """6x6 pill arrow, `found` — the off-clue givens force the pill to
    R2C4=1, R2C5=2 (place value 12) and the shaft to 1 + 6 + 5 = 12."""
    return _link(_PILL_GRID_FOUND, _PILL_BULB_RC, [_PILL_SHAFT_RC], box_h=2, box_w=3)


def broke_pill_arrow_6x6() -> str:
    """6x6 pill arrow, `broke` — the off-clue givens force the same pill
    (place value 12) but a shaft of 1 + 4 + 4 = 9."""
    return _link(_PILL_GRID_BROKE, _PILL_BULB_RC, [_PILL_SHAFT_RC], box_h=2, box_w=3)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-arrow-4x4": found_arrow_4x4,
    "broke-arrow-4x4": broke_arrow_4x4,
    "found-arrow-two-shafts-4x4": found_arrow_two_shafts_4x4,
    "found-pill-arrow-6x6": found_pill_arrow_6x6,
    "broke-pill-arrow-6x6": broke_pill_arrow_6x6,
}
