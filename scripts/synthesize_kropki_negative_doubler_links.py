"""Synthesize the white-kropki-negative-over-a-doubler-board corpus links in
code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

`differs_by`'s negated mode reads each pair through `engine.value_expr`
(ADR-0009), same as its positive mode — a doubler's `2·value`, never the raw
digit (`edge_clues_test.py`'s `test_kropki_negative_rule_composes_with_a_
doubler_or_s_cell_board` proves this at the decode/constraint-shape level).
This pair proves it end to end, through `cli.main`.

A 6x6 board (not 4x4, mirroring `found_schrodinger_6x6`'s reasoning): a 4x4
board pinned tight enough to force the doubler's placement transversal (one
modifier per row/column/box, ADR-0016) collides with the same givens a
kropki-negative fixture needs, leaving no digit choice that is both
board-feasible and decisive. The extra room on 6x6 avoids that collision
while keeping the target pair's verdict just as directly given-driven.

Both fixtures share one marked dot (R1C1/R1C2, diff 1) and one unmarked pair
(R4C4/R4C5) the `negative: [7]` rule reaches; only R4C5's given digit
changes, and R4C5 is the board's sole declared `Doubler`. On a 1-6 digit
domain a *raw* difference can never reach 7 — `negative: [7]` can only ever
fire against the *doubled* reading, so a broke verdict here is possible only
if the rule reads `2 * R4C5`, not R4C5's own digit. At R4C5 = 4 the doubled
value is 8, and `|1 - 8| = 7` is exactly the forbidden difference: `broke`.
Dropping the negative rule from that same board reads `found` — the break
rests on the rule alone, reading the doubled value. At R4C5 = 2 the doubled
value is 4 and `|1 - 4| = 3`, not forbidden: `found`.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.edge_clues import pair_to_edge
from gridfind.sudokumaker.wire_types import KROPKI_WHITE_TYPE

_SIZE = 6


def _link(*, r4c5: int) -> str:
    """Assemble a 6x6, 2x3-boxed document: a marked white-kropki dot on
    R1C1/R1C2 (diff 1, satisfied by the givens), a `negative: [7]` rule, a
    second given pair R4C4/R4C5 — an unmarked adjacency the rule reaches —
    and a `Doubler` marker cage declaring R4C5 a modifier, so the rule reads
    `2 * r4c5` rather than `r4c5` itself."""
    doubler_cell = row_col_to_index(4, 5, _SIZE)
    document = boxed_document(
        2,
        3,
        givens={(1, 1): 1, (1, 2): 2, (4, 4): 1, (4, 5): r4c5},
        constraints=[
            {
                "type": KROPKI_WHITE_TYPE,
                "clues": [{"value": 1, "edge": pair_to_edge(1, 1, _SIZE)}],
                "negative": [7],
            },
            {"name": "Doubler", "type": 2001, "cages": [{"cells": [doubler_cell]}]},
        ],
    )
    return document_to_link(document)


def found_kropki_negative_doubler_6x6() -> str:
    """6x6 white-kropki-negative over a doubler board, `found` — R4C5's
    doubled value is `2*2 = 4`, so R4C4/R4C5's real difference is 3, not the
    forbidden 7."""
    return _link(r4c5=2)


def broke_kropki_negative_doubler_6x6() -> str:
    """6x6 white-kropki-negative over a doubler board, `broke` — R4C5's
    doubled value is `2*4 = 8`, so R4C4/R4C5's real difference is 7, the sole
    forbidden value. A raw digit difference can never reach 7 on a 1-6
    domain, so this verdict is reachable only by reading the doubled value."""
    return _link(r4c5=4)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-kropki-negative-doubler-6x6": found_kropki_negative_doubler_6x6,
    "broke-kropki-negative-doubler-6x6": broke_kropki_negative_doubler_6x6,
}
