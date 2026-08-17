"""Synthesize the Rellik (anti-) cage corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what a
fixture exercises and regenerate the whole set with `main()`.

A `type 2001` cosmetic cage named `Rellik` graduates to a no-repeats `cage`
plus a `rellik-cage` over the same cells, its numeric `value` read as the
forbidden total (ADR-0018). Both
fixtures share the forbidden total 3 and a two-cell cage: `found` leaves the
cage's cells otherwise free, so a completion avoiding sum 3 exists (e.g.
`1, 4`); `broke` gives the same two cells `1, 2`, forcing the forbidden sum.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.layers.regions import box_regions, to_region_numbers
from gridfind.sudokumaker import encode_link
from gridfind.sudokumaker.addresses import cell_index

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

_BOX_H = 2
_BOX_W = 2
_SIZE = _BOX_H * _BOX_W

# The forbidden total both fixtures' cage carries — chosen so a two-cell
# cage over the 1..4 domain has exactly one digit pair that hits it ({1, 2}),
# leaving every other pair (e.g. {1, 4}) free.
_FORBIDDEN_TOTAL = 3


def _authored_cage_style() -> dict[str, object]:
    """The default black cosmetic-cage style SudokuMaker writes for a
    hand-drawn named cage — matches an authentic setter export rather than
    the style-less block SudokuMaker draws iconless. Display-only —
    `decode_link` never reads `style`."""
    return {"text": {"color": "#000000"}, "cage": {"color": "#000000"}}


def _document(
    *,
    givens: dict[tuple[int, int], int],
    cage_cells: list[tuple[int, int]],
    target: int,
) -> dict[str, object]:
    """A boxed 4x4 SudokuMaker document with `givens` (1-based `(row, col)` ->
    digit) and one `Rellik`-named cosmetic cage over `cage_cells`, labelled
    `target`."""
    cells: list[dict[str, object]] = [{} for _ in range(_SIZE * _SIZE)]
    for (row, col), value in givens.items():
        cells[cell_index(row, col, _SIZE)] = {"given": True, "value": value}
    region_numbers = to_region_numbers(_SIZE, box_regions(_SIZE, _BOX_H, _BOX_W))
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": region_numbers},
        {
            "name": "Rellik",
            "type": 2001,
            "cages": [
                {
                    "value": str(target),
                    "cells": [cell_index(r, c, _SIZE) for r, c in cage_cells],
                }
            ],
            "style": _authored_cage_style(),
        },
    ]
    puzzle = {"cells": cells, "size": _SIZE, "constraints": constraints}
    return {"formatVersion": "1.5.0", "puzzle": puzzle}


def found_rellik_4x4() -> str:
    """4x4, `found` — R1C1/R2C3 (different row, column, and box) carry a
    Rellik cage forbidding total 3. Otherwise blank, so the solver is free to
    complete them any distinct pair but {1, 2} — e.g. {1, 4} — while the rest
    of the grid fills in around them."""
    return encode_link(
        _document(givens={}, cage_cells=[(1, 1), (2, 3)], target=_FORBIDDEN_TOTAL)
    )


def broke_rellik_4x4() -> str:
    """4x4, `broke` — R1C1=1, R1C2=2 are settled givens under a Rellik cage
    over the same two cells forbidding total 3. The pair's sum is forced to
    exactly the forbidden total, so no completion exists."""
    return encode_link(
        _document(
            givens={(1, 1): 1, (1, 2): 2},
            cage_cells=[(1, 1), (1, 2)],
            target=_FORBIDDEN_TOTAL,
        )
    )


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-rellik-4x4": found_rellik_4x4,
    "broke-rellik-4x4": broke_rellik_4x4,
}


def main() -> None:
    """Regenerate every rellik corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
