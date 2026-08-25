"""Synthesize the length-2-thermo-over-a-doubler-board corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

`thermo` reads each path cell through `engine.value_expr` (ADR-0009), so a
length-2 thermo — a free inequality — over a doubler cell reads the doubled
value, not the raw digit (`thermo_test.py`'s
`test_thermo_reads_the_doubled_value_when_a_cell_is_the_modifier` proves this
at the layer-verdict seam). This pair proves it end to end, through
`cli.main`.

Both fixtures share one strict thermo R1C1 -> R1C2 (bulb R1C1) and a `Doubler`
marker cage naming R1C2 alone, which pins `is_modifier["R1C2"]` via the
decoded `ModifierDirective` (`applier.py`) — so R1C2's real value is
`2*digit`, not its raw digit. R1C1 is given 4, the top digit on a 1-4 board;
only R1C2's given digit changes.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import THERMO_TYPE

_SIZE = 4


def _link(*, r1c2: int) -> str:
    """Assemble a 4x4, 2x2-boxed document: a length-2 thermo R1C1 -> R1C2
    (bulb R1C1, given 4), and a `Doubler` marker cage naming R1C2 alone, so
    the edge reads `2 * r1c2` rather than `r1c2` itself."""
    path = [row_col_to_index(1, 1, _SIZE), row_col_to_index(1, 2, _SIZE)]
    doubler_cell = row_col_to_index(1, 2, _SIZE)
    document = boxed_document(
        2,
        2,
        givens={(1, 1): 4, (1, 2): r1c2},
        constraints=[
            {"type": THERMO_TYPE, "slow": False, "thermometers": [path]},
            {"name": "Doubler", "type": 2001, "cages": [{"cells": [doubler_cell]}]},
        ],
    )
    return document_to_link(document)


def found_thermo_doubler_4x4() -> str:
    """4x4 length-2 thermo over a doubler board, `found` — R1C2's doubled
    value is `2*3 = 6`, so R1C1 (4) < 6 holds."""
    return _link(r1c2=3)


def broke_thermo_doubler_4x4() -> str:
    """4x4 length-2 thermo over a doubler board, `broke` — R1C2's doubled
    value is `2*1 = 2`, so R1C1 (4) < 2 fails; both cells are given, so no
    completion can rescue the edge."""
    return _link(r1c2=1)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-thermo-doubler-4x4": found_thermo_doubler_4x4,
    "broke-thermo-doubler-4x4": broke_thermo_doubler_4x4,
}
