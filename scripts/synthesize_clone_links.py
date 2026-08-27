"""Synthesize the clone (`type 302`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

A clone block is `{type: 302, groups: [[cell indices], ...], style: {...}}` —
a flat, top-level `groups` list, each entry its own independent group whose
cells hold equal digit sets, no relationship to any other group in the
block (see `wire_types.CLONE_TYPE`). Every fixture clones a pair of
**non-attacking** cells (different row, column, and box), so the only rule
relating them is the clone: a divergent pair is `broke` because of the
clone, never because a house forbids the repeat.

The plain pair (`found`/`broke`) proves the digit copy; the S-cell pair proves
the digit-**set** read (ADR-0019 dec 4). Two distinct S-cells can never hold
equal digit sets on a valid board — every house holds exactly one S-cell, so
the S-cells form a rainbow transversal with distinct bases — so the S-cell case
is a `broke`: two S-cells pinned to different pairs, cloned, contradict. Drop
the clone and the board reads found, so the clone is the sole cause.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import authored_cage_style, boxed_document, grid_from_rows, off_path_givens

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import CLONE_TYPE

# R1C1 (index 0) and R3C3 (index 10) on a boxed 4x4: different row, column, and
# box, so nothing but a clone can relate them.
_A = 0
_B = 10
_A_RC = (1, 1)
_B_RC = (3, 3)

# Full, valid 4x4-box completions (spec #723 dec 3, ADR-style: verified via a
# throwaway backtracking solver, then confirmed against the actual verdict
# engine) with every cell but R1C1/R3C3 given, so those two cells are forced
# by ordinary row/column/box elimination alone rather than by a given sitting
# on the clone's own cells. `_FOUND_GRID` pins both to the same digit (1);
# `_BROKE_GRID` pins them to different digits (1 and 4).
_FOUND_GRID = grid_from_rows(
    [
        [1, 2, 3, 4],
        [4, 3, 2, 1],
        [2, 4, 1, 3],
        [3, 1, 4, 2],
    ]
)
_BROKE_GRID = grid_from_rows(
    [
        [1, 2, 3, 4],
        [3, 4, 1, 2],
        [2, 1, 4, 3],
        [4, 3, 2, 1],
    ]
)


def _clone_block(*groups: list[int]) -> dict[str, object]:
    """A `type 302` block over `groups`, each its own independent cell-index
    list, `style` carried through verbatim so the emitted link is authentic
    (`_corpus.authored_cage_style`'s reasoning, applied to clone's own real
    cosmetic value)."""
    return {
        "type": CLONE_TYPE,
        "groups": [list(group) for group in groups],
        "style": {"color": "#00000033"},
    }


def found_clone_4x4() -> str:
    """4x4, `found` — every cell but R1C1/R3C3 given from a real completion
    that forces both to 1 by ordinary row/column/box elimination alone; the
    clone's equal-digit requirement already holds between the two forced
    values, so the board completes."""
    return document_to_link(
        boxed_document(
            2,
            2,
            givens=off_path_givens(_FOUND_GRID, [_A_RC, _B_RC]),
            constraints=[_clone_block([_A, _B])],
        )
    )


def broke_clone_4x4() -> str:
    """4x4, `broke` — every cell but R1C1/R3C3 given from a real completion
    that forces R1C1 to 1 and R3C3 to 4 by ordinary row/column/box
    elimination alone: the clone requires equal digits, so no assignment
    satisfies it. Drop the clone and the forced pair reads found, so the
    clone is the sole cause."""
    return document_to_link(
        boxed_document(
            2,
            2,
            givens=off_path_givens(_BROKE_GRID, [_A_RC, _B_RC]),
            constraints=[_clone_block([_A, _B])],
        )
    )


def broke_clone_scell_4x4() -> str:
    """4x4, `broke` — R1C1 and R3C3 pinned as S-cells holding *different* pairs
    (`{0,1}` and `{0,2}`), then cloned. The clone requires equal digit sets, the
    marker cages force different ones, so the board is unsatisfiable. Drop the
    clone and each S-cell sits happily in its own house (found), so the clone is
    the sole cause — and the break proves the clone reads the S-cell's digit set,
    not a placement."""
    scell_cages = [
        {"value": "0,1", "cells": [_A]},
        {"value": "0,2", "cells": [_B]},
    ]
    return document_to_link(
        boxed_document(
            2,
            2,
            constraints=[
                {
                    "name": "S-cell",
                    "type": 2001,
                    "cages": scell_cages,
                    "style": authored_cage_style(),
                },
                _clone_block([_A, _B]),
            ],
        )
    )


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-clone-4x4": found_clone_4x4,
    "broke-clone-4x4": broke_clone_4x4,
    "broke-clone-scell-4x4": broke_clone_scell_4x4,
}
