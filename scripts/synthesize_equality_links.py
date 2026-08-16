"""Synthesize the equality-cage corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what
balance case a fixture exercises and regenerate the whole set with `main()`.

Both fixtures share one fully-given 4x4 solved grid, so the verdict never
depends on solving — only on whether the named `Equality` cosmetic cage's two
cells hold a balanced pair. On a 4-digit board (low `{1,2}`, high `{3,4}`),
the only pairs balancing both even/odd and low/high are `{1,4}` and `{2,3}`:
the found fixture cages such a pair, the broke fixture cages `{1,2}` — two
lows, no high, so `equality-cage` has no legal assignment.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.layers.regions import box_regions, to_region_numbers
from gridfind.sudokumaker import encode_link
from gridfind.sudokumaker.addresses import cell_index

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

# A solved 4x4 Latin grid respecting its 2x2 boxes, row-major.
_SOLUTION: list[list[int]] = [
    [1, 2, 3, 4],
    [3, 4, 1, 2],
    [2, 1, 4, 3],
    [4, 3, 2, 1],
]


def _link(*, cage_row: int, cage_cols: tuple[int, int]) -> str:
    """A fully-given 4x4 document (`_SOLUTION`) plus an `Equality`-named
    cosmetic cage over `cage_row`'s two `cage_cols` (1-based)."""
    size = 4
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    for row in range(1, size + 1):
        for col in range(1, size + 1):
            index = cell_index(row, col, size)
            cells[index] = {"given": True, "value": _SOLUTION[row - 1][col - 1]}
    region_numbers = to_region_numbers(size, box_regions(size, 2, 2))
    cage_indices = [cell_index(cage_row, col, size) for col in cage_cols]
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {
            "cells": cells,
            "size": size,
            "constraints": [
                {"type": 0},
                {"type": 1, "regions": region_numbers},
                {
                    "name": "Equality",
                    "type": 2001,
                    "cages": [{"cells": cage_indices}],
                },
            ],
        },
    }
    return encode_link(document)


def found_equality_4x4() -> str:
    """4x4 equality cage, `found` — R1C1=1 and R1C4=4 balance: one low, one
    high, one odd, one even. The rest of the grid is already given, so the
    puzzle solves trivially once the cage's own rule holds."""
    return _link(cage_row=1, cage_cols=(1, 4))


def broke_equality_4x4() -> str:
    """4x4 equality cage, `broke` — R1C1=1 and R1C2=2 are both low (`{1,2}`
    on a 4-digit board), so `equality-cage`'s `#low == 1` can never be met."""
    return _link(cage_row=1, cage_cols=(1, 2))


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-equality-4x4": found_equality_4x4,
    "broke-equality-4x4": broke_equality_4x4,
}


def main() -> None:
    """Regenerate every equality-cage corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
