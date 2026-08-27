"""Synthesize the labelled non-default kropki-value corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what value
a fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

Every existing white-kropki corpus link labels its dot with the default
difference (1), so a decoder that silently coerced `value` to that default
would still pass green — `edge_clues.kropki_constraints` honors a labelled
`value` verbatim (`pair-difference`'s `diff`), never assuming 1. The
`*-kropki-non-default-value-*` pair proves that at the link level: neither
fixture gives the dot's own two cells (R1C1/R1C2) directly (spec #723 dec 3,
issue #739) — each column is filled elsewhere so classic column
distinctness alone forces R1C1 and R1C2 to specific values, off the kropki
rule entirely. The `found-*` fixture's forced pair actually differs by 3,
matching the labelled value, so the link reads `found`; the `broke-*`
fixture's forced pair differs by 1 instead, satisfying only the *default*
difference, so the labelled-value dot reads `broke`. A decoder that coerced
the label to the default would invert both verdicts.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.edge_clues import pair_to_edge
from gridfind.sudokumaker.wire_types import KROPKI_WHITE_TYPE

# The labelled difference both fixtures' dot carries — anything but the
# default 1, so honoring it verbatim is the only way either fixture's
# verdict can be right.
_LABELLED_DIFF = 3


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
    document = boxed_document(
        box_h,
        box_w,
        givens=givens,
        constraints=[
            {
                "type": KROPKI_WHITE_TYPE,
                "clues": [
                    {
                        "value": _LABELLED_DIFF,
                        "edge": pair_to_edge(dot_row, dot_col, size),
                    }
                ],
                "negative": [],
            }
        ],
    )
    return document_to_link(document)


def found_kropki_non_default_value_4x4() -> str:
    """4x4 white-kropki, `found` — neither dot cell is given. Column 1's
    other three cells (2/3/4) force R1C1=1 by classic column distinctness;
    column 2's other three cells (3/1/2) force R1C2=4 the same way. The
    forced pair differs by 3, matching the dot's labelled value. Read
    `broke` if the label were coerced to the default difference 1 (1 and 4
    don't differ by 1)."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(2, 1): 2, (3, 1): 3, (4, 1): 4, (2, 2): 3, (3, 2): 1, (4, 2): 2},
        dot_row=1,
        dot_col=1,
    )


def broke_kropki_non_default_value_4x4() -> str:
    """4x4 white-kropki, `broke` — neither dot cell is given. Column 1's
    other three cells (3/2/4) force R1C1=1 by classic column distinctness;
    column 2's other three cells (4/1/3) force R1C2=2 the same way. The
    forced pair differs by 1, satisfying only the *default* difference, not
    the dot's labelled value 3. Read `found` if the label were coerced to
    the default instead of honored verbatim."""
    return _link(
        box_h=2,
        box_w=2,
        givens={(2, 1): 3, (3, 1): 2, (4, 1): 4, (2, 2): 4, (3, 2): 1, (4, 2): 3},
        dot_row=1,
        dot_col=1,
    )


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-kropki-non-default-value-4x4": found_kropki_non_default_value_4x4,
    "broke-kropki-non-default-value-4x4": broke_kropki_non_default_value_4x4,
}
