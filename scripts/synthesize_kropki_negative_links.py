"""Synthesize the white-kropki-negative corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `main()`.

Every other white-kropki corpus link carries an empty `negative: []`, so the
rule has never been proven end to end. Both fixtures below share one marked
dot (R1C1/R1C2, diff 1) and one unmarked pair (R3C3/R3C4) the `negative: [2]`
rule reaches; only R3C4's given changes between them — diff 1 (allowed) in
the found case, diff 2 (the forbidden value) in the broke case. Dropping the
`negative` list entirely (the old, unmodeled behaviour) resolves the broke
fixture's givens `found` instead, so the break is on the negative rule
alone, never on the classic or positive-clue constraints, which are
identical between the two fixtures.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.layers.regions import box_regions, to_region_numbers
from gridfind.sudokumaker import encode_link
from gridfind.sudokumaker.addresses import cell_index
from gridfind.sudokumaker.wire_types import KROPKI_WHITE_TYPE

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"


def _horizontal_edge(size: int, row: int, col: int) -> int:
    """The `edge` index of the horizontal pair starting at 1-based `(row,
    col)` and its right neighbor — `edge_clues._edge_to_pair`'s `edge =
    2*size*r0 + c0 + 1` formula, inverted for a known pair instead of a known
    edge."""
    r0, c0 = row - 1, col - 1
    return 2 * size * r0 + c0 + 1


def _link(*, r3c4: int) -> str:
    """Assemble a 4x4, 2x2-boxed document: a marked white-kropki dot on
    R1C1/R1C2 (diff 1, satisfied by the givens), a `negative: [2]` rule, and
    a second given pair R3C3/R3C4 — an unmarked adjacency the rule reaches —
    whose difference `r3c4` alone decides the verdict."""
    size = 4
    givens = {(1, 1): 1, (1, 2): 2, (3, 3): 1, (3, 4): r3c4}
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    for (row, col), value in givens.items():
        cells[cell_index(row, col, size)] = {"given": True, "value": value}
    region_numbers = to_region_numbers(size, box_regions(size, 2, 2))
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": region_numbers},
        {
            "type": KROPKI_WHITE_TYPE,
            "clues": [{"value": 1, "edge": _horizontal_edge(size, 1, 1)}],
            "negative": [2],
        },
    ]
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": size, "constraints": constraints},
    }
    return encode_link(document)


def found_kropki_negative_4x4() -> str:
    """4x4 white-kropki, `found` — R3C3/R3C4 differ by 1, not the forbidden
    2, so the negative rule has nothing to reject."""
    return _link(r3c4=2)


def broke_kropki_negative_4x4() -> str:
    """4x4 white-kropki, `broke` — R3C3/R3C4 differ by 2, the sole forbidden
    value, on an adjacency the marked dot doesn't cover. Read `found` if the
    negative list were dropped instead of enforced (the old behaviour)."""
    return _link(r3c4=3)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-kropki-negative-4x4": found_kropki_negative_4x4,
    "broke-kropki-negative-4x4": broke_kropki_negative_4x4,
}


def main() -> None:
    """Regenerate every white-kropki-negative corpus file from its
    synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
