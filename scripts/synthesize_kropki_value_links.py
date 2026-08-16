"""Synthesize the labelled non-default kropki-value corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what value
a fixture exercises and regenerate the whole set with `main()`.

Every existing white-kropki corpus link labels its dot with the default
difference (1), so a decoder that silently coerced `value` to that default
would still pass green — `edge_clues.kropki_constraints` honors a labelled
`value` verbatim (`pair-difference`'s `diff`), never assuming 1. The
`*-kropki-non-default-value-*` pair proves that at the link level: the same
two givens read `broke` under the labelled value 3 (their actual difference
is 1) and would read `found` if the decoder had coerced the label to the
default instead.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.sudokumaker import encode_link
from gridfind.sudokumaker.wire_types import KROPKI_WHITE_TYPE

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

# The labelled difference both fixtures' dot carries — anything but the
# default 1, so honoring it verbatim is the only way either fixture's
# verdict can be right.
_LABELLED_DIFF = 3


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


def _horizontal_edge(size: int, row: int, col: int) -> int:
    """The `edge` index of the horizontal pair starting at 1-based `(row,
    col)` and its right neighbor — `edge_clues._edge_to_pair`'s `edge =
    2*size*r0 + c0 + 1` formula, inverted for a known pair instead of a known
    edge."""
    r0, c0 = row - 1, col - 1
    return 2 * size * r0 + c0 + 1


def _link(
    *,
    box_h: int,
    box_w: int,
    givens: dict[tuple[int, int], int],
    dot_row: int,
    dot_col: int,
) -> str:
    """Assemble a boxed SudokuMaker document with the given clues and one
    white-kropki dot, labelled `_LABELLED_DIFF`, on the horizontal edge
    starting at `(dot_row, dot_col)`."""
    size = box_h * box_w
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    for (row, col), value in givens.items():
        cells[_index(size, row, col)] = {"given": True, "value": value}
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": _regions(box_h, box_w)},
        {
            "type": KROPKI_WHITE_TYPE,
            "clues": [
                {
                    "value": _LABELLED_DIFF,
                    "edge": _horizontal_edge(size, dot_row, dot_col),
                }
            ],
            "negative": [],
        },
    ]
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": size, "constraints": constraints},
    }
    return encode_link(document)


def found_kropki_non_default_value_4x4() -> str:
    """4x4 white-kropki, `found` — R1C1=1 and R1C2=4 differ by 3, matching
    the dot's labelled value. Read `broke` if the label were coerced to the
    default difference 1 (1 and 4 don't differ by 1)."""
    return _link(box_h=2, box_w=2, givens={(1, 1): 1, (1, 2): 4}, dot_row=1, dot_col=1)


def broke_kropki_non_default_value_4x4() -> str:
    """4x4 white-kropki, `broke` — R1C1=1 and R1C2=2 differ by 1, which
    satisfies the *default* difference but not the dot's labelled value 3.
    Read `found` if the label were coerced to the default instead of honored
    verbatim."""
    return _link(box_h=2, box_w=2, givens={(1, 1): 1, (1, 2): 2}, dot_row=1, dot_col=1)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-kropki-non-default-value-4x4": found_kropki_non_default_value_4x4,
    "broke-kropki-non-default-value-4x4": broke_kropki_non_default_value_4x4,
}


def main() -> None:
    """Regenerate every labelled-non-default-kropki-value corpus file from
    its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
