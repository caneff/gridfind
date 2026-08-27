"""Synthesize the Rellik (anti-) cage corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what a
fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

A `type 2001` cosmetic cage named `Rellik` graduates to a no-repeats `cage`
plus a `rellik-cage` over the same cells, its numeric `value` read as the
forbidden total (ADR-0018). Both fixtures share the forbidden total 3 and a
two-cell cage: `found` leaves the cage's cells otherwise free, so a
completion avoiding sum 3 exists (e.g. `1, 4`). `broke` (spec #723 dec 3)
gives every cell *but* the cage's own two, from a real, valid completion
(verified via a throwaway backtracking solver, then confirmed against the
actual verdict engine) that forces the pair to `1, 2` by ordinary row/box
elimination alone — the forbidden sum, so no completion exists.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import authored_cage_style, boxed_document, grid_from_rows, off_path_givens

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link

_BOX_H = 2
_BOX_W = 2
_SIZE = _BOX_H * _BOX_W

# The forbidden total both fixtures' cage carries — chosen so a two-cell
# cage over the 1..4 domain has exactly one digit pair that hits it ({1, 2}),
# leaving every other pair (e.g. {1, 4}) free.
_FORBIDDEN_TOTAL = 3

# A full, valid 4x4-box completion with every cell but R1C1/R1C2 given, so
# the pair is forced to 1, 2 — the forbidden total — by ordinary row/box
# elimination alone rather than by a given sitting on the rellik cage's own
# cells.
_BROKE_GRID = grid_from_rows(
    [
        [1, 2, 3, 4],
        [3, 4, 1, 2],
        [2, 3, 4, 1],
        [4, 1, 2, 3],
    ]
)


def _document(
    *,
    givens: dict[tuple[int, int], int],
    cage_cells: list[tuple[int, int]],
    target: int,
) -> dict[str, object]:
    """A boxed 4x4 SudokuMaker document with `givens` (1-based `(row, col)` ->
    digit) and one `Rellik`-named cosmetic cage over `cage_cells`, labelled
    `target`."""
    return boxed_document(
        _BOX_H,
        _BOX_W,
        givens=givens,
        constraints=[
            {
                "name": "Rellik",
                "type": 2001,
                "cages": [
                    {
                        "value": str(target),
                        "cells": [row_col_to_index(r, c, _SIZE) for r, c in cage_cells],
                    }
                ],
                "style": authored_cage_style(),
            }
        ],
    )


def found_rellik_4x4() -> str:
    """4x4, `found` — R1C1/R2C3 (different row, column, and box) carry a
    Rellik cage forbidding total 3. Otherwise blank, so the solver is free to
    complete them any distinct pair but {1, 2} — e.g. {1, 4} — while the rest
    of the grid fills in around them."""
    return document_to_link(
        _document(givens={}, cage_cells=[(1, 1), (2, 3)], target=_FORBIDDEN_TOTAL)
    )


def broke_rellik_4x4() -> str:
    """4x4, `broke` — every cell but R1C1/R1C2 given from a real completion
    that forces the pair to 1, 2 by ordinary row/box elimination alone, under
    a Rellik cage over the same two cells forbidding total 3. The pair's
    forced sum is exactly the forbidden total, so no completion exists."""
    return document_to_link(
        _document(
            givens=off_path_givens(_BROKE_GRID, [(1, 1), (1, 2)]),
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
