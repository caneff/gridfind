"""Synthesize the even/odd (`type 100`/`101`) corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what
each fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

One `found-`/`broke-` pair per parity, both over a single clued cell (R1C1)
on a boxed 4x4 board: the `found-*` fixture gives R1C1 a digit matching the
clue's parity, already satisfiable everywhere else (the rest of the board is
left to the solver); the `broke-*` fixture gives R1C1 the opposite parity, a
direct contradiction with the clue regardless of the rest of the board.

A third fixture, `broke-odd-doubler-4x4`, proves value-mode reading
(ADR-0009): R1C1 carries both an odd clue and a `Doubler` marker
cage, so its clue-relevant value is `value_expr`'s mapped `2·d`, always
even — unsatisfiable for every possible raw digit, with no given needed at
all.
"""

from __future__ import annotations

from collections.abc import Callable

from _corpus import boxed_document

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link
from gridfind.sudokumaker.wire_types import EVEN_TYPE, ODD_TYPE

_SIZE = 4
_CELL = row_col_to_index(1, 1, _SIZE)


def _link(wire_type: int, *, given: int | None = None, doubler: bool = False) -> str:
    """A boxed 4x4 SudokuMaker document with one even/odd block over R1C1,
    an optional given at R1C1, and an optional `Doubler` marker cage over the
    same cell."""
    constraints: list[dict[str, object]] = [{"type": wire_type, "cells": [_CELL]}]
    if doubler:
        constraints.append(
            {"name": "Doubler", "type": 2001, "cages": [{"cells": [_CELL]}]}
        )
    document = boxed_document(
        2,
        2,
        givens={} if given is None else {(1, 1): given},
        constraints=constraints,
    )
    return document_to_link(document)


def found_even_4x4() -> str:
    """4x4, `found` — R1C1 given 2 (even), an even clue over R1C1: satisfied."""
    return _link(EVEN_TYPE, given=2)


def broke_even_4x4() -> str:
    """4x4, `broke` — R1C1 given 1 (odd), an even clue over R1C1: a direct
    contradiction, unsatisfiable regardless of the rest of the board."""
    return _link(EVEN_TYPE, given=1)


def found_odd_4x4() -> str:
    """4x4, `found` — R1C1 given 1 (odd), an odd clue over R1C1: satisfied."""
    return _link(ODD_TYPE, given=1)


def broke_odd_4x4() -> str:
    """4x4, `broke` — R1C1 given 2 (even), an odd clue over R1C1: a direct
    contradiction, unsatisfiable regardless of the rest of the board."""
    return _link(ODD_TYPE, given=2)


def broke_odd_doubler_4x4() -> str:
    """4x4, `broke` — R1C1 is a `Doubler` with an odd clue: `value_expr`
    reads its mapped `2*d`, always even, so the odd clue is unsatisfiable no
    matter what digit the solver picks — the value-mode reading."""
    return _link(ODD_TYPE, doubler=True)


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-even-4x4": found_even_4x4,
    "broke-even-4x4": broke_even_4x4,
    "found-odd-4x4": found_odd_4x4,
    "broke-odd-4x4": broke_odd_4x4,
    "broke-odd-doubler-4x4": broke_odd_doubler_4x4,
}
