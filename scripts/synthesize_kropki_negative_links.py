"""Synthesize the white-kropki-negative corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Every other white-kropki corpus link carries an empty `negative: []`, so the
rule has never been proven end to end. Both fixtures below share one marked
dot (R1C1/R1C2, diff 1) and one unmarked pair (R3C3/R3C4) the `negative: [2]`
rule reaches; only R3C4's given changes between them — diff 1 (allowed) in
the found case, diff 2 (the forbidden value) in the broke case. The broke
fixture's givens resolve `found` when the negative rule is not enforced, so
the break rests on that rule alone, never on the classic or positive-clue
constraints, which are identical between the two fixtures.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.edge_clues import pair_to_edge
from gridfind.sudokumaker.wire_types import KROPKI_WHITE_TYPE

_SIZE = 4


def _link(*, r3c4: int) -> str:
    """Assemble a 4x4, 2x2-boxed document: a marked white-kropki dot on
    R1C1/R1C2 (diff 1, satisfied by the givens), a `negative: [2]` rule, and
    a second given pair R3C3/R3C4 — an unmarked adjacency the rule reaches —
    whose difference `r3c4` alone decides the verdict."""
    document = boxed_document(
        2,
        2,
        givens={(1, 1): 1, (1, 2): 2, (3, 3): 1, (3, 4): r3c4},
        constraints=[
            {
                "type": KROPKI_WHITE_TYPE,
                "clues": [{"value": 1, "edge": pair_to_edge(1, 1, _SIZE)}],
                "negative": [2],
            }
        ],
    )
    return document_to_link(document)


def found_kropki_negative_4x4() -> str:
    """4x4 white-kropki, `found` — R3C3/R3C4 differ by 1, not the forbidden
    2, so the negative rule has nothing to reject."""
    return _link(r3c4=2)


def broke_kropki_negative_4x4() -> str:
    """4x4 white-kropki, `broke` — R3C3/R3C4 differ by 2, the sole forbidden
    value, on an adjacency the marked dot doesn't cover. Without the negative
    rule these same givens read `found`, so the verdict flips on that rule
    alone."""
    return _link(r3c4=3)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-kropki-negative-4x4": found_kropki_negative_4x4,
    "broke-kropki-negative-4x4": broke_kropki_negative_4x4,
}
