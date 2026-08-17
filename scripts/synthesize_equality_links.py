"""Synthesize the equality-cage corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what balance
case a fixture exercises and regenerate the whole set with `main()`.

Every fixture is a sparse 9x9 with row 1 holding the only givens. A broke
fixture gives row 1's five non-cage columns their own digit (`1..9` is a legal
first row), forcing the four empty cage cells to the complementary set — the
exact digits that violate a clause. The found fixture instead gives two of the
cage's own cells and lets the equality rule force the other two, so the cage
balances and the solver completes an otherwise empty grid. Either way the
verdict turns on the cage, proven by a real solve.

A 9-digit board splits low `{1,2,3,4}` / high `{6,7,8,9}` with `5` the middle
value in neither half. An equality cage of `N` cells demands `#even == N/2`,
`#low == N/2`, and `#high == N/2` — three independent clauses. The row-1 cage
placements below pick digit sets that isolate each break: only a board with a
middle value can satisfy `#low` while failing `#high` (the `middle` case),
which is why the corpus lives at 9x9, not 4x4.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.cell_geometry import row_col_to_index
from gridfind.layers.regions import box_regions
from gridfind.sudokumaker import document_to_link

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

_SIZE = 9


def _link(*, cage_cols: tuple[int, ...], givens: tuple[tuple[int, int], ...]) -> str:
    """A sparse 9x9 document with an `Equality`-named cosmetic cage over row 1's
    `cage_cols` cells. `givens` is `(col, value)` pairs placed in row 1, the only
    filled cells; rows 2-9 stay empty."""
    cage_index_list = [row_col_to_index(1, col, _SIZE) for col in cage_cols]
    cells: list[dict[str, object]] = [{} for _ in range(_SIZE * _SIZE)]
    for col, value in givens:
        cells[row_col_to_index(1, col, _SIZE)] = {"given": True, "value": value}
    region_numbers = box_regions(_SIZE, 3, 3).to_labels(_SIZE)
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {
            "cells": cells,
            "size": _SIZE,
            "constraints": [
                {"type": 0},
                {"type": 1, "regions": region_numbers},
                {
                    "name": "Equality",
                    "type": 2001,
                    "cages": [{"cells": cage_index_list}],
                },
            ],
        },
    }
    return document_to_link(document)


def _broke(cage_cols: tuple[int, ...]) -> str:
    """A broke fixture: give row 1's non-`cage_cols` columns their own digit, so
    the four empty cage cells are forced to the complementary set `{cage_cols}` —
    the exact digits that violate a clause."""
    cage_set = set(cage_cols)
    givens = tuple((col, col) for col in range(1, _SIZE + 1) if col not in cage_set)
    return _link(cage_cols=cage_cols, givens=givens)


def found_equality_9x9() -> str:
    """`found` — cage over row 1 cols (1,4,6,7), with two of its own cells given
    `2` and `4` (both low, both even) and nothing else on the board. The equality
    rule forces the remaining two cage cells to be odd and high — uniquely the
    pair `{7,9}` — so the cage balances (`#even`=2, `#low`=2, `#high`=2) and the
    solver completes an otherwise empty grid."""
    return _link(cage_cols=(1, 4, 6, 7), givens=((1, 2), (4, 4)))


def broke_equality_parity_9x9() -> str:
    """`broke` on parity alone — cage forced to `{2,4,6,7}`: `#low`=2 (2,4) and
    `#high`=2 (6,7) both hold, but `#even`=3 (2,4,6) != 2. Isolates the
    `#even == N/2` clause."""
    return _broke((2, 4, 6, 7))


def broke_equality_rank_9x9() -> str:
    """`broke` on rank alone — cage forced to `{1,2,3,4}`: `#even`=2 (2,4) holds,
    but all four are low, so `#low`=4 and `#high`=0. Isolates the low/high
    clause."""
    return _broke((1, 2, 3, 4))


def broke_equality_middle_9x9() -> str:
    """`broke` on the high clause via the middle value — cage forced to
    `{2,4,5,7}`: `#even`=2 (2,4) and `#low`=2 (2,4) both hold, but `5` is the
    middle value in neither half, so `#high`=1 (7) != 2. Only a board with a
    middle value can satisfy `#low` yet fail `#high`, so this case is unreachable
    below 9x9."""
    return _broke((2, 4, 5, 7))


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-equality-9x9": found_equality_9x9,
    "broke-equality-parity-9x9": broke_equality_parity_9x9,
    "broke-equality-rank-9x9": broke_equality_rank_9x9,
    "broke-equality-middle-9x9": broke_equality_middle_9x9,
}


def main() -> None:
    """Regenerate every equality-cage corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
