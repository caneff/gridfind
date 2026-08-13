"""Fill a found link's witness back in as an openable SudokuMaker solution-link.

A dev tool, on demand only (`just verify-links`) — the human oracle spec
#244/ADR-0007 asks for: over every case file under `links/`, decode and
verdict the link exactly as `links_test.py` does. A `found` link's witness
digits are written into the link's own decoded document as givens and
re-encoded via `encode_link`, so the printed link opens in the app with the
answer already filled in — reusing the original document keeps the fields
(`size`, `type`) the app needs to render the real puzzle. A `broke` link
prints `broke` and no URL, since there is no witness to show.

    uv run python scripts/verify_links.py
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from gridfind.layers.board import cell_address
from gridfind.sudokumaker import (
    decode_document,
    decode_link,
    encode_link,
    is_scell_marker_name,
    write_cell,
)
from gridfind.verdict import verdict
from gridfind.witness import Witness

LINKS_DIR = Path(__file__).parent.parent / "src" / "gridfind" / "links"


def fill_witness(
    document: dict[str, object], witness: Witness, size: int
) -> dict[str, object]:
    """`document` with every cell overwritten by its witness content,
    addressed by the same row-major `i // size`, `i % size` scheme
    `decode_link` reads cells with. Each cell is written through `write_cell`,
    the decoder's one wire-write seam — a singleton digit becomes a given, a
    Schrödinger pair its red two-mark pin, and a cell the solver found to be a
    modifier (doubler) carries the red bit too — so this holds no knowledge of
    the cell's field shape. Every other field of `document` rides through
    untouched, so `size`/`type` survive and the emitted link opens as the same
    puzzle.

    `decode_link` sources an S-cell's pair from its marker cage's own `value`
    (spec #349), not the cell's cosmetic candidates `write_cell` paints — so
    every S-cell marker cage is also stamped with its solved pair
    (`_stamp_scell_cage_values`), the write-side mirror of that read, keeping
    the emitted link's own re-decode agree with the witness it was built
    from."""
    filled: dict[str, object] = json.loads(json.dumps(document))
    puzzle_data = cast("dict[str, object]", filled["puzzle"])
    cells = cast("list[dict[str, Any]]", puzzle_data["cells"])
    for i, cell in enumerate(cells):
        address = cell_address(i // size + 1, i % size + 1)
        write_cell(cell, witness[address], is_modifier=address in witness.modifiers)
    _stamp_scell_cage_values(puzzle_data, witness, size)
    return filled


def _stamp_scell_cage_values(
    puzzle_data: dict[str, object], witness: Witness, size: int
) -> None:
    """Every `S-cell`/`Schrödinger` marker cage's `value` set to its solved
    pair `"a,b"`, so the emitted link's own re-decode reads the same pin
    `write_cell` painted onto the cells for SudokuMaker's display (spec #349).
    A cage whose cells disagree (only reachable from a bare multi-cell cage,
    where each cell is independently free) is left as-is rather than guessing
    one pair for cells that solved to different ones."""
    constraints = puzzle_data.get("constraints", [])
    if not isinstance(constraints, list):
        return
    for block in constraints:
        if not isinstance(block, dict) or block.get("disabled") is True:
            continue
        if not is_scell_marker_name(block.get("name")):
            continue
        for cage in cast("list[dict[str, Any]]", block.get("cages", [])):
            addresses = [
                cell_address(i // size + 1, i % size + 1) for i in cage["cells"]
            ]
            pairs = {witness[address] for address in addresses}
            if len(pairs) == 1:
                (pair,) = pairs
                if len(pair) == 2:
                    a, b = pair
                    cage["value"] = f"{a},{b}"


def verify_link(argv: Sequence[str]) -> str:
    """One case file's argv (the link is the last token, matching
    `links_test.py`'s loader) reduced to the emitter's report: a found link's
    solution-link, or `broke` when the verdict is anything else — a link corpus
    is curated found/broke by filename, so an off-corpus `unknown` reports the
    same as `broke` rather than implying a witness that was never computed."""
    link = argv[-1]
    puzzle, state = decode_link(link)
    result = verdict(puzzle, state)
    if result.kind != "found" or result.witness is None:
        return "broke"
    return emit_solution_link(link, result.witness, puzzle.board.size)


def emit_solution_link(link: str, witness: Witness, size: int) -> str:
    """A found link's `witness` re-emitted as an openable SudokuMaker
    solution-link: the link's own decoded document with every cell filled from
    the witness (`fill_witness`), re-encoded. The one home for the fill+encode
    step, shared by the verify oracle and the eval view so a caller holding a
    witness need not solve the puzzle again to show its answer.

    The board `size` is stamped explicitly so the link opens at the right
    dimensions even when the source omitted it — SudokuMaker reads a sizeless
    link as its 9x9 default (§4b, ADR-0011)."""
    document = decode_document(link)
    filled = fill_witness(document, witness, size)
    cast("dict[str, object]", filled["puzzle"])["size"] = size
    return encode_link(filled)


def main() -> int:
    for path in sorted(LINKS_DIR.rglob("*.txt")):
        argv = path.read_text().split()
        print(f"{path.stem}: {verify_link(argv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
