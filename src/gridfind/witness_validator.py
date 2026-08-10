"""An independent check of a rendered witness grid against the puzzle that
produced it (spec #185, issue #186).

`validate_witness` reverses `Witness.render()` enough to recover the grid of
digits, then checks it directly: right size, every cell in the board's digit
domain, every row/column/region a permutation of it, and every given sitting
in its cell. It reads a `Puzzle` (typically `sudokumaker.decode_link`'s
output) but never calls `verdict()` and never touches `Witness` or its
`render()` — so a defect in the solver or the renderer can't hide behind a
witness that merely *looks* right to the same code that produced it.

Regions come straight off the puzzle's own `regions-distinct` constraint —
bare (the board's box tiling, via `region_map_for`) or jigsaw
(`params["regions"]`, via `region_map_from_labels`) — the same two shapes
`decode_link` itself ever emits, so this stays in lockstep with the decoder
without importing anything from the verdict/render path.
"""

from __future__ import annotations

import re

from gridfind.layers.regions import RegionMap, region_map_for, region_map_from_labels
from gridfind.puzzle import Puzzle

_DIGIT_RE = re.compile(r"\d+")
_ADDRESS_RE = re.compile(r"R(\d+)C(\d+)")


def validate_witness(rendered: str, puzzle: Puzzle) -> bool:
    """`True` when `rendered` (a `Witness.render()` string) is a legal
    completion of `puzzle`. `False` on any violation, including a grid whose
    shape doesn't even parse as `puzzle.board.size`x`size`."""
    size = puzzle.board.size
    grid = _parse_grid(rendered, size)
    if grid is None:
        return False

    domain = frozenset(puzzle.board.values)
    if any(digit not in domain for row in grid for digit in row):
        return False

    columns = [[grid[row][col] for row in range(size)] for col in range(size)]
    regions = _regions(puzzle, size, grid)
    if any(frozenset(group) != domain for group in (*grid, *columns, *regions)):
        return False

    for given in puzzle.givens:
        row, col = _parse_address(given.address)
        if grid[row - 1][col - 1] != given.digit:
            return False
    return True


def _parse_grid(rendered: str, size: int) -> list[list[int]] | None:
    """The rendered box-drawing grid, read back into a `size`x`size` array of
    digits: `n+1` border lines interleave with `n` cell lines (issue #124's
    render shape), so the cell lines are every other line starting at index
    1. `None` when the text doesn't have that many lines, or a cell line
    doesn't hold exactly `size` digit tokens — a shape mismatch is a
    validation failure, not a crash."""
    lines = [line for line in rendered.split("\n") if line]
    if len(lines) != 2 * size + 1:
        return None
    grid = []
    for line in lines[1::2]:
        digits = [int(token) for token in _DIGIT_RE.findall(line)]
        if len(digits) != size:
            return None
        grid.append(digits)
    return grid


def _regions(puzzle: Puzzle, size: int, grid: list[list[int]]) -> list[list[int]]:
    region_map = _region_map(puzzle, size)
    if region_map is None:
        return []
    return [[grid[row - 1][col - 1] for row, col in group] for group in region_map]


def _region_map(puzzle: Puzzle, size: int) -> RegionMap | None:
    for constraint in puzzle.constraints:
        if constraint.type == "regions-distinct":
            if "regions" in constraint.params:
                return region_map_from_labels(size, constraint.params["regions"])
            return region_map_for(size)
    return None


def _parse_address(address: str) -> tuple[int, int]:
    match = _ADDRESS_RE.fullmatch(address)
    if match is None:
        msg = f"malformed cell address: {address!r}"
        raise ValueError(msg)
    return int(match.group(1)), int(match.group(2))
