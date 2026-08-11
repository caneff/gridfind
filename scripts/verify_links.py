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
import urllib.parse
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from lzstring import LZString

from gridfind.layers.board import cell_address
from gridfind.sudokumaker import decode_link, encode_link
from gridfind.verdict import verdict
from gridfind.witness import Witness

LINKS_DIR = Path(__file__).parent.parent / "src" / "gridfind" / "links"

# SudokuMaker's S-cell color bit, matching `gridfind.sudokumaker._RED_BIT` —
# the channel `decode_link` reads a Schrödinger S-cell's pair back from.
_RED_BIT = 2


def _decode_document(link: str) -> dict[str, object]:
    """The full decoded link JSON (`formatVersion` plus its `puzzle` block),
    mirroring `decode_link`'s own payload step — kept local since
    `decode_link` returns a `Puzzle`, not the document `encode_link` needs
    back to preserve every field a real link carries."""
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    # Decoded JSON is an untyped external boundary — a local `Any` is
    # deliberate (CODING_STANDARDS: reach for `Any` only at genuine
    # boundaries).
    data: Any = json.loads(raw)
    return data


def fill_witness(
    document: dict[str, object], witness: Witness, size: int
) -> dict[str, object]:
    """`document` with every cell overwritten by its witness content,
    addressed by the same row-major `i // size`, `i % size` scheme
    `decode_link` reads cells with. A singleton digit becomes an ordinary
    given (`given: True, value: d`), read back through `decode_link`'s
    `given` branch. A Schrödinger S-cell's pair `(a, b)` is written through
    the red-color + candidate-bitmask channel `decode_link` reads it back
    from — the `_RED_BIT` bit set in `colors`, both digits set in
    `candidates` — the inverse of that decode. Every other field of
    `document` rides through untouched, so `size`/`type` survive and the
    emitted link opens as the same puzzle."""
    filled: dict[str, object] = json.loads(json.dumps(document))
    puzzle_data = cast("dict[str, object]", filled["puzzle"])
    cells = cast("list[dict[str, object]]", puzzle_data["cells"])
    for i, cell in enumerate(cells):
        address = cell_address(i // size + 1, i % size + 1)
        content = witness[address]
        if len(content) == 1:
            cell["given"] = True
            cell["value"] = content[0]
        else:
            a, b = content
            cell["colors"] = cast("int", cell.get("colors", 0)) | _RED_BIT
            cell["candidates"] = (1 << a) | (1 << b)
    return filled


def verify_link(argv: Sequence[str]) -> str:
    """One case file's argv (flags then the link, matching `links_test.py`'s
    loader) reduced to the emitter's report: a found link's solution-link, or
    `broke` when the verdict is anything else — a link corpus is curated
    found/broke by filename, so an off-corpus `unknown` reports the same as
    `broke` rather than implying a witness that was never computed."""
    schrodinger = "--schrodinger" in argv
    link = argv[-1]
    puzzle, state = decode_link(link, schrodinger=schrodinger)
    result = verdict(puzzle, state)
    if result.kind != "found" or result.witness is None:
        return "broke"
    document = _decode_document(link)
    filled = fill_witness(document, result.witness, puzzle.board.size)
    return encode_link(filled)


def main() -> int:
    for path in sorted(LINKS_DIR.rglob("*.txt")):
        argv = path.read_text().split()
        print(f"{path.stem}: {verify_link(argv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
