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
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document, off_path_givens

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
    bulb_rc: tuple[int, int],
    shafts_rc: list[list[tuple[int, int]]],
) -> str:
    """A boxed 4x4 SudokuMaker document with one arrow — `bulb_rc` and one or
    more `shafts_rc` paths — given every cell of `grid` except the clue's own
    bulb and shaft cells."""
    clue_cells = [bulb_rc, *(cell for shaft in shafts_rc for cell in shaft)]
    bulb_index = row_col_to_index(*bulb_rc, _SIZE)
    shaft_indices = [
        [row_col_to_index(*cell, _SIZE) for cell in shaft] for shaft in shafts_rc
    ]
    document = boxed_document(
        2,
        2,
        givens=off_path_givens(grid, clue_cells),
        constraints=[
            {
                "type": ARROW_TYPE,
                "bulbsWithArrows": [
                    {"bulbCells": [bulb_index], "arrows": shaft_indices}
                ],
            }
        ],
    )
    return document_to_link(document)


def found_arrow_4x4() -> str:
    """4x4 arrow, `found` — the off-clue givens force the bulb to 4 and the
    shaft to 1 + 3 = 4."""
    return _link(_GRID_FOUND, _BULB_RC, [_SHAFT_RC])


def broke_arrow_4x4() -> str:
    """4x4 arrow, `broke` — the off-clue givens force the same bulb (4) but
    a shaft of 2 + 1 = 3."""
    return _link(_GRID_BROKE, _BULB_RC, [_SHAFT_RC])


def found_arrow_two_shafts_4x4() -> str:
    """4x4 arrow with two shafts on one bulb, `found` — the off-clue givens
    force the bulb to 4, the one-cell shaft to 4, and the two-cell shaft to
    2 + 2 = 4: both shafts hold independently."""
    return _link(
        _GRID_TWO_SHAFTS,
        _TWO_SHAFT_BULB_RC,
        [_TWO_SHAFT_FIRST_RC, _TWO_SHAFT_SECOND_RC],
    )


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-arrow-4x4": found_arrow_4x4,
    "broke-arrow-4x4": broke_arrow_4x4,
    "found-arrow-two-shafts-4x4": found_arrow_two_shafts_4x4,
}
