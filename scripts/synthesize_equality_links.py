"""Synthesize the equality-cage corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what balance
case a fixture exercises and regenerate the whole set with `main()`.

Every fixture shares one solved 9x9 grid, given in full **except** the cage
cells, which are left empty. The solver must place them, and column/box
constraints force each back to its solution value — so the named `Equality`
cage sees a known digit set and the verdict turns on whether that set balances,
proven by a real solve rather than a rubber-stamped board.

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

from gridfind.layers.regions import box_regions, to_region_numbers
from gridfind.sudokumaker import encode_link
from gridfind.sudokumaker.addresses import cell_index

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

_SIZE = 9

# A solved 9x9 grid (band-shifted rows), row-major. Row 1 is the identity
# `1..9`, so a cage over columns `cols` in row 1 encloses exactly the digit set
# `cols` — the placement lever every fixture below pulls.
_SOLUTION: list[list[int]] = [
    [(3 * (row % 3) + row // 3 + col) % 9 + 1 for col in range(_SIZE)]
    for row in range(_SIZE)
]


def _link(*, cage_cols: tuple[int, ...]) -> str:
    """A 9x9 document given in full except row 1's `cage_cols` (1-based), which
    are left empty and enclosed in an `Equality`-named cosmetic cage. The empty
    cells force back to their solution digits (the column values `cage_cols`),
    so the cage judges that digit set."""
    cage_index_list = [cell_index(1, col, _SIZE) for col in cage_cols]
    cage_indices = set(cage_index_list)
    cells: list[dict[str, object]] = [{} for _ in range(_SIZE * _SIZE)]
    for row in range(1, _SIZE + 1):
        for col in range(1, _SIZE + 1):
            index = cell_index(row, col, _SIZE)
            if index in cage_indices:
                continue
            cells[index] = {"given": True, "value": _SOLUTION[row - 1][col - 1]}
    region_numbers = to_region_numbers(_SIZE, box_regions(_SIZE, 3, 3))
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
    return encode_link(document)


def found_equality_9x9() -> str:
    """`found` — cage over `{1,4,6,7}`: `#even`=2 (4,6), `#low`=2 (1,4),
    `#high`=2 (6,7). Every clause holds, so the forced grid is a legal
    completion."""
    return _link(cage_cols=(1, 4, 6, 7))


def broke_equality_parity_9x9() -> str:
    """`broke` on parity alone — cage over `{2,4,6,7}`: `#low`=2 (2,4) and
    `#high`=2 (6,7) both hold, but `#even`=3 (2,4,6) != 2. Isolates the
    `#even == N/2` clause."""
    return _link(cage_cols=(2, 4, 6, 7))


def broke_equality_rank_9x9() -> str:
    """`broke` on rank alone — cage over `{1,2,3,4}`: `#even`=2 (2,4) holds,
    but all four are low, so `#low`=4 and `#high`=0. Isolates the low/high
    clause."""
    return _link(cage_cols=(1, 2, 3, 4))


def broke_equality_middle_9x9() -> str:
    """`broke` on the high clause via the middle value — cage over `{2,4,5,7}`:
    `#even`=2 (2,4) and `#low`=2 (2,4) both hold, but `5` is the middle value in
    neither half, so `#high`=1 (7) != 2. Only a board with a middle value can
    satisfy `#low` yet fail `#high`, so this case is unreachable below 9x9."""
    return _link(cage_cols=(2, 4, 5, 7))


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
