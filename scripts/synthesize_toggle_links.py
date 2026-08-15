"""Synthesize the global-toggle corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what each
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
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

# The toggle wire types are imported from the decoder — their one home — so the
# corpus builds off the same numbers the decoder reads by, never a second copy.
from gridfind.sudokumaker import (
    _ANTI_KING_TYPE,
    _ANTI_KNIGHT_TYPE,
    _NEGATIVE_DIAGONAL_TYPE,
    _POSITIVE_DIAGONAL_TYPE,
    encode_link,
)

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

# The cosmetic style SudokuMaker writes onto a diagonal block. Display-only —
# `decode_link` ignores it — but carried so the emitted link matches the app's.
_DIAGONAL_STYLE = {"color": "#34bbe6ff", "thickness": 0.02}


def _regions(box_h: int, box_w: int) -> list[int]:
    """The classic box tiling of a `box_h`x`box_w`-box board as SudokuMaker's
    flat, row-major region-id array — the `type 1` matrix a boxed link ships."""
    size = box_h * box_w
    boxes_per_row = size // box_w
    labels = [0] * (size * size)
    for row in range(size):
        for col in range(size):
            labels[row * size + col] = (row // box_h) * boxes_per_row + col // box_w
    return labels


def _index(size: int, row: int, col: int) -> int:
    """The flat row-major cell index of 1-based `RxCy` on a size-N board."""
    return (row - 1) * size + (col - 1)


def _toggle_block(wire_type: int) -> dict[str, object]:
    """One SudokuMaker toggle constraint block. The diagonals carry the app's
    cosmetic style; the anti-knight/anti-king toggles are bare."""
    if wire_type in (_NEGATIVE_DIAGONAL_TYPE, _POSITIVE_DIAGONAL_TYPE):
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
        cells[_index(size, row, col)] = {"given": True, "value": value}
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": _regions(box_h, box_w)},
        *(_toggle_block(wire_type) for wire_type in toggles),
    ]
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": size, "constraints": constraints},
    }
    return encode_link(document)


def found_anti_knight_4x4() -> str:
    """4x4 anti-knight, `found` — two clues the anti-knight rule leaves
    solvable."""
    return _link(
        box_h=2, box_w=2, givens={(1, 1): 1, (1, 2): 2}, toggles=[_ANTI_KNIGHT_TYPE]
    )


def broke_anti_knight_4x4() -> str:
    """4x4 anti-knight, `broke` — R1C1 and R3C2 are a knight's hop apart and
    hold the same digit: legal under classic, forbidden under anti-knight."""
    return _link(
        box_h=2, box_w=2, givens={(1, 1): 1, (3, 2): 1}, toggles=[_ANTI_KNIGHT_TYPE]
    )


def found_anti_king_6x6() -> str:
    """6x6 anti-king, `found` — a 4x4 has no anti-king solution (its boxes
    force a diagonal repeat), so the anti-king pair lives on a 6x6."""
    return _link(box_h=2, box_w=3, givens={(1, 1): 1}, toggles=[_ANTI_KING_TYPE])


def broke_anti_king_6x6() -> str:
    """6x6 anti-king, `broke` — R2C3 and R3C4 are a king's step apart in
    different boxes and hold the same digit: legal under classic, forbidden
    under anti-king."""
    return _link(
        box_h=2, box_w=3, givens={(2, 3): 1, (3, 4): 1}, toggles=[_ANTI_KING_TYPE]
    )


def found_x_sudoku_4x4() -> str:
    """4x4 X-sudoku, `found` — both diagonals enabled, two clues the diagonals
    leave solvable."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 1): 1, (1, 2): 2},
        toggles=[_NEGATIVE_DIAGONAL_TYPE, _POSITIVE_DIAGONAL_TYPE],
    )


def broke_x_sudoku_4x4() -> str:
    """4x4 X-sudoku, `broke` — R1C1 and R3C3 share the negative diagonal (`\\`)
    and hold the same digit: legal under classic, forbidden once it is on."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(1, 1): 1, (3, 3): 1},
        toggles=[_NEGATIVE_DIAGONAL_TYPE, _POSITIVE_DIAGONAL_TYPE],
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
}


def main() -> None:
    """Regenerate every toggle corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
