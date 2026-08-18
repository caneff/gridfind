"""Fill a found link's witness back in as an openable SudokuMaker solution-link.

A dev tool, on demand only (`just verify-links`) — the human oracle
ADR-0007 asks for: over every case file under `links/`, decode and
verdict the link exactly as `links_test.py` does. A `found` link's witness
digits are written into the link's own decoded document as givens and
re-encoded via `document_to_link`, so the printed link opens in the app with the
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

from gridfind.cell_geometry import format_address
from gridfind.sudokumaker import (
    colorize_marker_cages,
    cosmetic_cage_kind,
    document_to_link,
    link_to_document,
    link_to_puzzle,
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
    `link_to_puzzle` reads cells with. Each cell is written through `write_cell`,
    the decoder's one wire-write seam — a singleton digit becomes a given, a
    Schrödinger pair its two center marks — so this holds no knowledge of the
    cell's field shape. Every other field of `document` rides through
    untouched, so `size`/`type` survive and the emitted link opens as the same
    puzzle.

    The solver discovers S-cells and modifiers (doublers or constants) the
    source link never declared, and gridfind reads them only from named marker
    cages, never cell colors — so `_mark_witness_variants` extends each marker
    block to cover every variant cell the witness holds. A discovered S-cell
    joins the `S-cell` block as a single-cell cage carrying its solved pair;
    a discovered modifier joins its marker block's cage. The
    emitted solution then marks every S-cell and modifier by cage alone, and
    its own re-decode agrees with the witness it was built from."""
    filled: dict[str, object] = json.loads(json.dumps(document))
    puzzle_data = cast("dict[str, object]", filled["puzzle"])
    cells = cast("list[dict[str, Any]]", puzzle_data["cells"])
    for i, cell in enumerate(cells):
        address = format_address(i // size + 1, i % size + 1)
        write_cell(cell, witness[address])
    _mark_witness_variants(puzzle_data, witness, size)
    return filled


def _mark_witness_variants(
    puzzle_data: dict[str, object], witness: Witness, size: int
) -> None:
    """Extend each named marker block to cover every variant cell the witness
    holds, so the emitted link marks S-cells and modifiers by cage alone. The
    `S-cell` block gains a single-cell cage per witness S-cell not already
    caged, each stamped with its solved pair `"a,b"`; an existing cage whose
    cells solved to one pair is stamped too, and a cage whose cells disagree
    (only reachable from a bare multi-cell cage) is left as-is. The modifier
    block (`Doubler` or `Constant`) gains every witness modifier cell it
    lacks."""
    constraints = puzzle_data.get("constraints", [])
    if not isinstance(constraints, list):
        return
    index_of = {
        format_address(i // size + 1, i % size + 1): i for i in range(size * size)
    }
    for block in constraints:
        if not isinstance(block, dict) or block.get("disabled") is True:
            continue
        typed_block = cast("dict[str, Any]", block)
        kind = cosmetic_cage_kind(block.get("name"))
        if kind == "s-cell":
            _mark_scell_block(typed_block, witness, size, index_of)
        elif kind in ("doubler", "constant"):
            _mark_modifier_block(typed_block, witness, index_of)


def _mark_scell_block(
    block: dict[str, Any], witness: Witness, size: int, index_of: dict[str, int]
) -> None:
    """Stamp each existing S-cell cage with its solved pair and append a
    single-cell cage for every witness S-cell (a length-2 assignment) not yet
    covered, so all S-cells are marked by cage."""
    cages = cast("list[dict[str, Any]]", block.setdefault("cages", []))
    covered: set[int] = set()
    for cage in cages:
        covered.update(cage["cells"])
        addresses = [format_address(i // size + 1, i % size + 1) for i in cage["cells"]]
        pairs = {witness[address] for address in addresses}
        if len(pairs) == 1:
            (pair,) = pairs
            if len(pair) == 2:
                a, b = pair
                cage["value"] = f"{a},{b}"
    for address, content in witness.assignment.items():
        index = index_of[address]
        if len(content) == 2 and index not in covered:
            a, b = content
            cages.append({"value": f"{a},{b}", "cells": [index]})


def _mark_modifier_block(
    block: dict[str, Any], witness: Witness, index_of: dict[str, int]
) -> None:
    """Fold every witness modifier cell into the marker block's single cage, so
    all modifiers the solver found — doublers or constants — are marked by
    cage. A link carries only one modifier type, so its witness modifiers are
    all that type."""
    cages = cast("list[dict[str, Any]]", block.setdefault("cages", [{"cells": []}]))
    cage = cages[0]
    modifiers = {index_of[address] for address in witness.modifiers}
    cage["cells"] = sorted(set(cage.get("cells", [])) | modifiers)


def oracle_witness(link: str) -> tuple[str, Witness | None, int]:
    """Decode `link`, verdict it, and apply the ADR-0007 link-oracle guard: a
    witness is returned only for a `found` verdict that actually carries one,
    since a found-but-unwitnessed result has nothing for a caller to show. The
    one home for decode → verdict → guard, shared by the verify oracle
    (`verify_link`) and the eval view (`eval_links.eval_link`)."""
    puzzle, state = link_to_puzzle(link)
    result = verdict(puzzle, state)
    if result.kind != "found" or result.witness is None:
        return result.kind, None, puzzle.board.size
    return result.kind, result.witness, puzzle.board.size


def verify_link(argv: Sequence[str]) -> str:
    """One case file's argv (the link is the last token, matching
    `links_test.py`'s loader) reduced to the emitter's report: a found link's
    solution-link, or `broke` when the verdict is anything else — a link corpus
    is curated found/broke by filename, so an off-corpus `unknown` reports the
    same as `broke` rather than implying a witness that was never computed."""
    link = argv[-1]
    _, witness, size = oracle_witness(link)
    if witness is None:
        return "broke"
    return emit_solution_link(link, witness, size)


def emit_solution_link(link: str, witness: Witness, size: int) -> str:
    """A found link's `witness` re-emitted as an openable SudokuMaker
    solution-link: the link's own decoded document with every cell filled from
    the witness (`fill_witness`), its named marker cages colored
    (`colorize_marker_cages`), re-encoded. The one home for the fill+color+
    encode step, shared by the verify oracle and the eval view so a caller
    holding a witness need not solve the puzzle again to show its answer.

    The board `size` is stamped explicitly so the link opens at the right
    dimensions even when the source omitted it — SudokuMaker reads a sizeless
    link as its 9x9 default (§4b, ADR-0011)."""
    document = link_to_document(link)
    filled = fill_witness(document, witness, size)
    cast("dict[str, object]", filled["puzzle"])["size"] = size
    return document_to_link(colorize_marker_cages(filled))


def main() -> int:
    for path in sorted(LINKS_DIR.rglob("*.txt")):
        argv = path.read_text().split()
        print(f"{path.stem}: {verify_link(argv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
