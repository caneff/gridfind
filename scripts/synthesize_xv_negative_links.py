"""Synthesize the xv-negative corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

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

from _corpus import boxed_document

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import XV_TYPE


def _link(*, r3c4: int) -> str:
    """Assemble a 4x4, 2x2-boxed document: a bare `negative: [5]` XV block
    (no positive clues) and one given pair, R3C3/R3C4, whose sum with `r3c4`
    alone decides the verdict."""
    document = boxed_document(
        2,
        2,
        givens={(3, 3): 3, (3, 4): r3c4},
        constraints=[{"type": XV_TYPE, "clues": [], "negative": [5]}],
    )
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
