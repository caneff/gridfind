"""Synthesize the xv-negative corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `main()`.

Unlike the white-/black-kropki-negative fixtures, this pair carries no marked
XV clue: on a 4x4 board (digits 1-4), a valid classic-plus-2x2-box grid can
carry a two-cell adjacent sum of 5 at most zero or four times (never
exactly one — a parity artifact of the two sum-5 digit pairs, {1,4} and
{2,3}, confirmed by brute-force enumeration), so no grid admits one marked
V clue (a sum-5 pair) with every *other* adjacent pair sum-5-free. `negative:
[5]` alone, with an empty `clues` list, is still a fully valid type-202
block — the mechanism reads `marked` as empty and treats every
orthogonally-adjacent pair as eligible. Both fixtures share the same two
givens, R3C3 and R3C4, drawn from one of the eight zero-sum5-edge completions
of the board (found by the same enumeration); only R3C4 changes between
them — 1 (so R3C3/R3C4 sum to 4, allowed) in the found case, 2 (sum to 5, the
forbidden value) in the broke case, which is rejected by the rule at that
pair alone regardless of how the rest of the board could be filled.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.cell_geometry import row_col_to_index
from gridfind.layers.regions import box_regions, to_region_numbers
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import XV_TYPE

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"


def _link(*, r3c4: int) -> str:
    """Assemble a 4x4, 2x2-boxed document: a bare `negative: [5]` XV block
    (no positive clues) and one given pair, R3C3/R3C4, whose sum with `r3c4`
    alone decides the verdict."""
    size = 4
    givens = {(3, 3): 3, (3, 4): r3c4}
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    for (row, col), value in givens.items():
        cells[row_col_to_index(row, col, size)] = {"given": True, "value": value}
    region_numbers = to_region_numbers(size, box_regions(size, 2, 2))
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": region_numbers},
        {"type": XV_TYPE, "clues": [], "negative": [5]},
    ]
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": size, "constraints": constraints},
    }
    return document_to_link(document)


def found_xv_negative_4x4() -> str:
    """4x4 XV, `found` — R3C3/R3C4 sum to 4, not the forbidden 5, and the
    rest of the board completes to one of the grids with no other
    adjacent-sum-5 pair."""
    return _link(r3c4=1)


def broke_xv_negative_4x4() -> str:
    """4x4 XV, `broke` — R3C3/R3C4 sum to 5, the sole forbidden value, on an
    adjacency no positive clue covers. Without the negative rule these same
    givens read `found`, so the verdict flips on that rule alone."""
    return _link(r3c4=2)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-xv-negative-4x4": found_xv_negative_4x4,
    "broke-xv-negative-4x4": broke_xv_negative_4x4,
}


def main() -> None:
    """Regenerate every xv-negative corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
