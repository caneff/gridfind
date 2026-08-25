"""Synthesize the black-kropki-negative corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Mirrors `synthesize_kropki_negative_links.py`'s white-kropki fixtures, one
relation-value up: both fixtures share one marked dot (R1C1/R1C2, ratio 2)
and one unmarked pair (R3C3/R3C4) the `negative: [3]` rule reaches; only
R3C4's given changes between them — ratio 2 (allowed) in the found case,
ratio 3 (the forbidden value) in the broke case. The broke fixture's givens
resolve `found` when the negative rule is not enforced, so the break rests
on that rule alone, never on the classic or positive-clue constraints, which
are identical between the two fixtures.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.edge_clues import pair_to_edge
from gridfind.sudokumaker.wire_types import KROPKI_BLACK_TYPE

_SIZE = 4


def _link(*, r3c4: int) -> str:
    """Assemble a 4x4, 2x2-boxed document: a marked black-kropki dot on
    R1C1/R1C2 (ratio 2, satisfied by the givens), a `negative: [3]` rule, and
    a second given pair R3C3/R3C4 — an unmarked adjacency the rule reaches —
    whose ratio to `r3c4` alone decides the verdict."""
    document = boxed_document(
        2,
        2,
        givens={(1, 1): 1, (1, 2): 2, (3, 3): 1, (3, 4): r3c4},
        constraints=[
            {
                "type": KROPKI_BLACK_TYPE,
                "clues": [{"value": 2, "edge": pair_to_edge(1, 1, _SIZE)}],
                "negative": [3],
            }
        ],
    )
    return document_to_link(document)


def found_black_kropki_negative_4x4() -> str:
    """4x4 black-kropki, `found` — R3C3/R3C4 are in ratio 2, not the
    forbidden 3, so the negative rule has nothing to reject."""
    return _link(r3c4=2)


def broke_black_kropki_negative_4x4() -> str:
    """4x4 black-kropki, `broke` — R3C3/R3C4 are in ratio 3, the sole
    forbidden value, on an adjacency the marked dot doesn't cover. Without
    the negative rule these same givens read `found`, so the verdict flips
    on that rule alone."""
    return _link(r3c4=3)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-black-kropki-negative-4x4": found_black_kropki_negative_4x4,
    "broke-black-kropki-negative-4x4": broke_black_kropki_negative_4x4,
}
