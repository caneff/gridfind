"""Synthesize the global-toggle corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `main()`.

These fixtures cover the three global toggles gridfind reads off real
SudokuMaker links: anti-knight (`type 13`), anti-king (`type 12`), and the two
independent diagonals — negative `\\` (`type 10`) and positive `/` (`type 11`),
which together make X-sudoku. The wire types were read from setter-supplied
links, not guessed.

Each `broke-*` fixture holds two plain givens that are legal under classic
sudoku but collide under the toggle — a knight's hop, a king's step, or a
shared diagonal — so the puzzle breaks *because of* the toggle, not the givens
alone. Each `found-*` fixture is a lightly-clued board the toggle leaves
solvable. Anti-king has no solution on a 4x4 (the boxes force a diagonal
repeat), so its pair lives on a 6x6, where an anti-king solution exists.

The two diagonals are independent switches, but both x-sudoku fixtures carry
both at once — a decoder that swapped or dropped one diagonal would still
pass green. The `*-negative-diagonal-only-*`/`*-positive-diagonal-only-*`
fixtures each set exactly one diagonal toggle, so a collision on that
diagonal alone can only turn `broke` if the switch decoded to the right one.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.cell_geometry import row_col_to_index

# The toggle wire types are imported from wire_types.py — their one shared
# home — so the corpus builds off the same numbers the decoder reads by,
# never a second copy.
from gridfind.layers.regions import box_regions
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import (
    ANTI_KING_TYPE,
    ANTI_KNIGHT_TYPE,
    NEGATIVE_DIAGONAL_TYPE,
    POSITIVE_DIAGONAL_TYPE,
)

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

# The cosmetic style SudokuMaker writes onto a diagonal block. Display-only —
# `link_to_puzzle` ignores it — but carried so the emitted link matches the app's.
_DIAGONAL_STYLE = {"color": "#34bbe6ff", "thickness": 0.02}


def _toggle_block(wire_type: int) -> dict[str, object]:
    """One SudokuMaker toggle constraint block. The diagonals carry the app's
    cosmetic style; the anti-knight/anti-king toggles are bare."""
    if wire_type in (NEGATIVE_DIAGONAL_TYPE, POSITIVE_DIAGONAL_TYPE):
        return {"type": wire_type, "style": dict(_DIAGONAL_STYLE)}
    return {"type": wire_type}


def _link(
    *,
    box_h: int,
    box_w: int,
    givens: dict[tuple[int, int], int],
    toggles: list[int],
) -> str:
    """Assemble a boxed SudokuMaker document with the given clues and toggle
    blocks, then encode it to an openable link."""
    size = box_h * box_w
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    for (row, col), value in givens.items():
        cells[row_col_to_index(row, col, size)] = {"given": True, "value": value}
    region_numbers = box_regions(size, box_h, box_w).to_labels(size)
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": region_numbers},
        *(_toggle_block(wire_type) for wire_type in toggles),
    ]
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": size, "constraints": constraints},
    }
    return document_to_link(document)


def found_anti_knight_4x4() -> str:
    """4x4 anti-knight, `found` — two clues the anti-knight rule leaves
    solvable."""
    return _link(
        box_h=2, box_w=2, givens={(1, 1): 1, (1, 2): 2}, toggles=[ANTI_KNIGHT_TYPE]
    )


def broke_anti_knight_4x4() -> str:
    """4x4 anti-knight, `broke` — R1C1 and R3C2 are a knight's hop apart and
    hold the same digit: legal under classic, forbidden under anti-knight."""
    return _link(
        box_h=2, box_w=2, givens={(1, 1): 1, (3, 2): 1}, toggles=[ANTI_KNIGHT_TYPE]
    )


def found_anti_king_6x6() -> str:
    """6x6 anti-king, `found` — a 4x4 has no anti-king solution (its boxes
    force a diagonal repeat), so the anti-king pair lives on a 6x6."""
    return _link(box_h=2, box_w=3, givens={(1, 1): 1}, toggles=[ANTI_KING_TYPE])


def broke_anti_king_6x6() -> str:
    """6x6 anti-king, `broke` — R2C3 and R3C4 are a king's step apart in
    different boxes and hold the same digit: legal under classic, forbidden
    under anti-king."""
    return _link(
        box_h=2, box_w=3, givens={(2, 3): 1, (3, 4): 1}, toggles=[ANTI_KING_TYPE]
    )


def found_x_sudoku_4x4() -> str:
    """4x4 X-sudoku, `found` — both diagonals enabled, two clues the diagonals
    leave solvable."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 1): 1, (1, 2): 2},
        toggles=[NEGATIVE_DIAGONAL_TYPE, POSITIVE_DIAGONAL_TYPE],
    )


def broke_x_sudoku_4x4() -> str:
    """4x4 X-sudoku, `broke` — R1C1 and R3C3 share the negative diagonal (`\\`)
    and hold the same digit: legal under classic, forbidden once it is on."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 1): 1, (3, 3): 1},
        toggles=[NEGATIVE_DIAGONAL_TYPE, POSITIVE_DIAGONAL_TYPE],
    )


def found_negative_diagonal_only_4x4() -> str:
    """4x4, `found` — only the negative diagonal (`\\`) toggle is on, the
    positive diagonal left off, so type 10 is exercised alone."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 1): 1, (1, 2): 2},
        toggles=[NEGATIVE_DIAGONAL_TYPE],
    )


def broke_negative_diagonal_only_4x4() -> str:
    """4x4, `broke` — only the negative diagonal toggle is on. R1C1 and R3C3
    share the negative diagonal and hold the same digit; the same pair does
    not share the positive diagonal, so a decoder that swapped or dropped the
    diagonal would leave this `found`, not `broke`."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 1): 1, (3, 3): 1},
        toggles=[NEGATIVE_DIAGONAL_TYPE],
    )


def found_positive_diagonal_only_4x4() -> str:
    """4x4, `found` — only the positive diagonal (`/`) toggle is on, the
    negative diagonal left off, so type 11 is exercised alone."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 1): 1, (1, 2): 2},
        toggles=[POSITIVE_DIAGONAL_TYPE],
    )


def broke_positive_diagonal_only_4x4() -> str:
    """4x4, `broke` — only the positive diagonal toggle is on. R1C4 and R3C2
    share the positive diagonal and hold the same digit; the same pair does
    not share the negative diagonal, so a decoder that swapped or dropped the
    diagonal would leave this `found`, not `broke`."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 4): 1, (3, 2): 1},
        toggles=[POSITIVE_DIAGONAL_TYPE],
    )


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-anti-knight-4x4": found_anti_knight_4x4,
    "broke-anti-knight-4x4": broke_anti_knight_4x4,
    "found-anti-king-6x6": found_anti_king_6x6,
    "broke-anti-king-6x6": broke_anti_king_6x6,
    "found-x-sudoku-4x4": found_x_sudoku_4x4,
    "broke-x-sudoku-4x4": broke_x_sudoku_4x4,
    "found-negative-diagonal-only-4x4": found_negative_diagonal_only_4x4,
    "broke-negative-diagonal-only-4x4": broke_negative_diagonal_only_4x4,
    "found-positive-diagonal-only-4x4": found_positive_diagonal_only_4x4,
    "broke-positive-diagonal-only-4x4": broke_positive_diagonal_only_4x4,
}


def main() -> None:
    """Regenerate every toggle corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
