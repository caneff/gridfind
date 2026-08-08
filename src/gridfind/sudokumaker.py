"""Decode a SudokuMaker share link into gridfind's `Puzzle` + `WorkingState`.

One pure function, `decode_link`, mirroring `puzzle.py`'s schema-only role: it
strips the `?puzzle=` payload, lz-string-decompresses it, and maps the
`formatVersion 1.5.0` JSON to the model per the confirmed field-by-field map in
`docs/research/sudoku-link-formats.md` §4a (issue #54). Classic 9x9 only — a
non-classic link (a variant domain, jigsaw regions, an unknown ruleset) is
rejected with `ValueError` rather than mis-decoded into a confident wrong verdict.

No engine, no `verdict` call. Schema in, model out.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from lzstring import LZString

from gridfind.layers.board import cell_name
from gridfind.layers.regions import classic_region_map
from gridfind.puzzle import (
    Board,
    Candidate,
    Constraint,
    Given,
    Place,
    Puzzle,
    WorkingState,
)

# The decoder is classic-9x9-only (issue #77 leaves it untouched) — its own
# constant, not the board layer's (which now derives size from the puzzle).
BOARD_SIZE = 9
CELL_COUNT = BOARD_SIZE * BOARD_SIZE
# The digit domain of a classic (1-9). Bit 0 of a candidates/corner mask is only
# meaningful for a `minDigit:0` variant, which the guard rejects (§4a).
_DIGITS = range(1, BOARD_SIZE + 1)

# SudokuMaker leaves rows/cols implicit under `type 0`; gridfind makes all three
# explicit. Emitted in this order.
_CLASSIC_CONSTRAINTS = (
    Constraint("rows-distinct"),
    Constraint("cols-distinct"),
    Constraint("regions-distinct"),
)

# The standard 3x3 box partition as SudokuMaker's flat 81-array of region ids,
# row-major — a `type 1` `regions` matrix that differs is jigsaw, out of scope.
_CLASSIC_REGIONS = [0] * CELL_COUNT
for _region_id, _box in enumerate(classic_region_map(BOARD_SIZE)):
    for _row, _col in _box:
        _CLASSIC_REGIONS[(_row - 1) * BOARD_SIZE + (_col - 1)] = _region_id


def decode_link(link: str) -> tuple[Puzzle, WorkingState]:
    """Map a SudokuMaker `?puzzle=` link (or a bare payload) to a classic 9x9
    `Puzzle` + `WorkingState`. Raises `ValueError` on a non-classic link."""
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    puzzle_data: Any = json.loads(raw)["puzzle"]
    _reject_non_classic(puzzle_data)

    cells = puzzle_data["cells"]
    givens: list[Given] = []
    places: list[Place] = []
    candidates: list[Candidate] = []
    for i, cell in enumerate(cells):
        address = cell_name(i // BOARD_SIZE + 1, i % BOARD_SIZE + 1)
        if "value" in cell:
            if cell.get("given"):
                givens.append(Given(address, cell["value"]))
            else:
                places.append(Place(address, cell["value"]))
        elif "candidates" in cell:
            digits = frozenset(d for d in _DIGITS if cell["candidates"] & (1 << d))
            candidates.append(Candidate(address, digits))
        # cornerPencilMarks, colors, and {} carry nothing gridfind can represent.

    puzzle = Puzzle(
        board=Board(size=BOARD_SIZE),
        constraints=_CLASSIC_CONSTRAINTS,
        givens=tuple(givens),
    )
    return puzzle, WorkingState(places=tuple(places), candidates=tuple(candidates))


def _reject_non_classic(puzzle_data: dict[str, object]) -> None:
    """Guard the classic 9x9 boundary: refuse a variant domain, a non-81 grid,
    an unknown ruleset, or jigsaw regions (§4a). Narrows the untyped JSON as it
    checks — a shape that isn't a classic's is exactly what it rejects."""
    if _has_key(puzzle_data, ("minDigit", "maxDigit")):
        msg = "non-classic link: a minDigit/maxDigit domain is a variant"
        raise ValueError(msg)
    cells = puzzle_data.get("cells")
    if not isinstance(cells, list) or len(cells) != CELL_COUNT:
        msg = f"non-classic link: expected {CELL_COUNT} cells"
        raise ValueError(msg)
    constraints = puzzle_data.get("constraints", [])
    if not isinstance(constraints, list):
        return
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        kind = constraint.get("type")
        if kind not in (0, 1):
            msg = f"non-classic link: unknown constraint type {kind!r}"
            raise ValueError(msg)
        if kind == 1 and constraint.get("regions") != _CLASSIC_REGIONS:
            msg = "non-classic link: regions are not the standard 3x3 partition"
            raise ValueError(msg)


def _has_key(value: object, keys: tuple[str, ...]) -> bool:
    """True if any of `keys` appears anywhere in the nested JSON `value`."""
    if isinstance(value, dict):
        return any(k in value for k in keys) or any(
            _has_key(v, keys) for v in value.values()
        )
    if isinstance(value, list):
        return any(_has_key(item, keys) for item in value)
    return False
