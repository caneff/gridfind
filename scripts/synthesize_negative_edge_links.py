"""Synthesize the negative-edge-clue corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `main()`.

Every kropki/XV corpus link elsewhere carries an empty `negative: []` — the
"absence of a dot/clue forbids the relation" rule is unmodeled, so
`_edge_clue_constraints` only warns and drops it (`_warn_dropped_negative`).
These fixtures are the first to carry a non-empty `negative` list, proving
that path end-to-end: decode still succeeds, the positive clue still drives
the verdict, and the drop is visible only as a stderr warning. White-kropki
(`type 200`) covers the shared wire shape XV and black-kropki also carry
(issue #487: any one of the three is sufficient).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.sudokumaker import encode_link
from gridfind.sudokumaker.wire_types import KROPKI_WHITE_TYPE

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"


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


def _link(*, givens: dict[tuple[int, int], int], negative: list[int]) -> str:
    """Assemble a 4x4, 2x2-boxed SudokuMaker document carrying one
    white-kropki clue at edge 1 (R1C1/R1C2, diff 1) alongside a non-empty
    `negative` list, then encode it to an openable link."""
    size = 4
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    for (row, col), value in givens.items():
        cells[_index(size, row, col)] = {"given": True, "value": value}
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": _regions(2, 2)},
        {
            "type": KROPKI_WHITE_TYPE,
            "clues": [{"value": 1, "edge": 1}],
            "negative": negative,
        },
    ]
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": size, "constraints": constraints},
    }
    return encode_link(document)


def found_kropki_negative_4x4() -> str:
    """4x4 white-kropki, `found` — same givens/clue as `found-kropki-4x4`,
    plus a `negative` mark on edge 2 (R1C2/R1C3): the mark is dropped
    (warn-only), so the positive diff-1 clue alone still leaves this
    solvable."""
    return _link(givens={(1, 3): 3, (2, 1): 3}, negative=[2])


def broke_kropki_negative_4x4() -> str:
    """4x4 white-kropki, `broke` — same givens/clue as `broke-kropki-4x4`,
    plus a `negative` mark on edge 2: the mark plays no part in the break,
    which still comes from the positive diff-1 clue alone."""
    return _link(givens={(1, 3): 2, (1, 4): 4}, negative=[2])


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-kropki-negative-4x4": found_kropki_negative_4x4,
    "broke-kropki-negative-4x4": broke_kropki_negative_4x4,
}


def main() -> None:
    """Regenerate every negative-edge-clue corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
