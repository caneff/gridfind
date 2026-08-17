"""Synthesize the official somedoku found/broke corpus pair in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what each
fixture exercises and regenerate the whole set with `main()`.

The document is the setter's own Somedoku template, captured verbatim in
`somedoku_template.json` and re-encoded with each fixture's givens. A real
Somedoku puzzle is a standalone grid: its only constraint is the `type 1000`
custom constraint named `Somedoku` (`definition.name`), which carries the
full component definition SudokuMaker needs to register and render it
(ADR-0017). It has **no** `type 1` regions block and no boxes — so the
template carries none, and the synthesized links open on SudokuMaker.com
exactly as the setter's do. gridfind recognizes somedoku by the constraint's
name alone; it never reads the component's programmed logic, cells, or value.

`found-somedoku-9x9` is the blank template — zero givens, which the
row-*n*/col-*n* distinct-count rule alone leaves solvable. `broke-somedoku-9x9`
adds two givens in column 1 — column 1's target is 1 distinct digit, but two
different given digits already force 2, so it breaks on the column pass
alone (ADR-0017) while every row still carries at most its own single given
digit.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gridfind.cell_geometry import row_col_to_index
from gridfind.sudokumaker import document_to_link

_HERE = Path(__file__).resolve().parent
LINKS_DIR = _HERE.parent / "src" / "gridfind" / "links"
_TEMPLATE_PATH = _HERE / "somedoku_template.json"

_SIZE = 9


def _template() -> dict[str, Any]:
    """The setter's own blank Somedoku document — its full `type 1000`
    definition and no regions block — loaded fresh so each caller mutates a
    private copy. `Any` values: it is opaque parsed JSON we only re-encode."""
    return json.loads(_TEMPLATE_PATH.read_text())


def _link(givens: dict[tuple[int, int], int]) -> str:
    """Re-encode the Somedoku template with the given clues to an openable
    link. Every non-given cell stays the template's empty `{}`."""
    document = _template()
    cells: list[dict[str, object]] = [{} for _ in range(_SIZE * _SIZE)]
    for (row, col), value in givens.items():
        cells[row_col_to_index(row, col, _SIZE)] = {"given": True, "value": value}
    document["puzzle"]["cells"] = cells
    return document_to_link(document)


def found_somedoku_9x9() -> str:
    """9x9 somedoku, `found` — the blank template, zero givens; the
    row-n/col-n distinct-count rule alone is satisfiable."""
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
