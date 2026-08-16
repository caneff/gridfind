"""Synthesize the official somedoku found/broke corpus pair in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `main()`.

Somedoku declares itself through a `type 1000` custom constraint named
`Somedoku` (`definition.name`) — the carrier the setter's real link uses
(spec #436, grilling #405): a programmed SudokuMaker constraint gridfind
cannot execute, recognized by name alone. A standard 9x9 `type 1` regions
block rides alongside it, exactly as a setter's own document carries one
regardless of variant; `decode_link` skips it once the somedoku flag is
read, since a somedoku grid has no boxes.

`found-somedoku-9x9` mirrors the setter's real link: zero givens, which the
row-*n*/col-*n* distinct-count rule alone leaves solvable. `broke-somedoku-9x9`
adds two givens in column 1 — column 1's target is 1 distinct digit, but two
different given digits already force 2, so it breaks on the column pass
alone (#512) while every row still carries at most its own single given
digit.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.layers.regions import box_regions, to_region_numbers
from gridfind.sudokumaker import encode_link
from gridfind.sudokumaker.addresses import cell_index
from gridfind.sudokumaker.wire_types import CUSTOM_CONSTRAINT_TYPE

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

_SIZE = 9
_BOX_H = 3
_BOX_W = 3


def _somedoku_block() -> dict[str, object]:
    """The `type 1000` custom-constraint carrier a setter's own Somedoku
    puzzle uses — its cells and value are noise `decode_link` never reads,
    so only `definition.name` is load-bearing."""
    return {"type": CUSTOM_CONSTRAINT_TYPE, "definition": {"name": "Somedoku"}}


def _link(givens: dict[tuple[int, int], int]) -> str:
    """Assemble a 9x9 SudokuMaker document carrying the given clues and the
    Somedoku flag, then encode it to an openable link."""
    cells: list[dict[str, object]] = [{} for _ in range(_SIZE * _SIZE)]
    for (row, col), value in givens.items():
        cells[cell_index(row, col, _SIZE)] = {"given": True, "value": value}
    region_numbers = to_region_numbers(_SIZE, box_regions(_SIZE, _BOX_H, _BOX_W))
    document = {
        "formatVersion": "1.5.0",
        "puzzle": {
            "cells": cells,
            "size": _SIZE,
            "constraints": [
                {"type": 0},
                {"type": 1, "regions": region_numbers},
                _somedoku_block(),
            ],
        },
    }
    return encode_link(document)


def found_somedoku_9x9() -> str:
    """9x9 somedoku, `found` — zero givens, mirroring the setter's real
    link; the row-n/col-n distinct-count rule alone is satisfiable."""
    return _link(givens={})


def broke_somedoku_9x9() -> str:
    """9x9 somedoku, `broke` — R1C1 and R2C1 are two different digits in
    column 1, whose target is 1 distinct digit: broken by the column pass
    alone, with every row still satisfiable on its own single given."""
    return _link(givens={(1, 1): 1, (2, 1): 2})


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`); the
# drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-somedoku-9x9": found_somedoku_9x9,
    "broke-somedoku-9x9": broke_somedoku_9x9,
}


def main() -> None:
    """Regenerate every somedoku corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
