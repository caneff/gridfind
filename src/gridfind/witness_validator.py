"""An independent check of a rendered witness grid against the puzzle that
produced it.

Test-only support, not public API: imported solely by the e2e suite, and kept
out of the shipped wheel via `source-exclude` in pyproject.toml.

`validate_witness` reverses `Witness.render()` enough to recover the grid of
cells, then checks it directly: right size, every cell's digit(s) in the
board's domain, every row/column/region a permutation of it — each checked
only when the puzzle's own constraints actually carry that rule
(`rows-distinct`/`cols-distinct`/`regions-distinct`), the same conditional
reading `_regions` already gives regions, since a puzzle can hold one without
the other (a somedoku puzzle carries neither, running on `line-count-distinct`
instead) — and every given sitting in its cell. It reads a `Puzzle`
(typically `sudokumaker.decode_link`'s output) but never calls `verdict()`
and never touches `Witness` or its `render()` — so a defect in the solver or
the renderer can't hide behind a witness that merely *looks* right to the
same code that produced it.

The parse below reads against `grid_text.py`'s line/token shape, not against
`witness.py` itself — that contract is the one place both sides
cite, so a layout drift in `render()` fails this parse loudly (`None`, then
`False`) instead of silently reading the wrong cells.

Regions come straight off the puzzle's own `regions-distinct` constraint, via
`region_map_for_constraints` (one door: bare resolves to the board's box tiling, jigsaw
to `params["regions"]`) — the same shapes
`decode_link` itself ever emits, so this stays in lockstep with the decoder.
That resolver is the same one the witness render path crosses, so a
render → validate round-trip proves both sides agree on one partition
instead of each re-deriving it.

A cell parses as a 1-tuple for an ordinary digit or a 2-tuple for a
Schrödinger S-cell's rendered pair `{a b}` (`grid_text.format_cell`'s
inverse). The permutation check flattens each row/column/region's cells to
individual digits before comparing against the domain — for an all-singleton
group that is exactly the digit list itself, so a classic puzzle's check is
unchanged; for a Schrödinger group, a house's digit slots (`d0` always, `d1`
for its one S-cell) must land on each domain digit exactly once
(`emit_house`), so the same "flatten, then must equal the
domain with no repeats" check covers both without a schrodinger branch.
"""

from __future__ import annotations

from gridfind import grid_text
from gridfind.cell_geometry import _row_col
from gridfind.layers.regions import region_map_for_constraints
from gridfind.puzzle import Puzzle

Cell = tuple[int, ...]


def validate_witness(rendered: str, puzzle: Puzzle) -> bool:
    """`True` when `rendered` (a `Witness.render()` string) is a legal
    completion of `puzzle`. `False` on any violation, including a grid whose
    shape doesn't even parse as `puzzle.board.size`x`size`."""
    size = puzzle.board.size
    grid = _parse_grid(rendered, size)
    if grid is None:
        return False

    domain = frozenset(puzzle.board.values)
    if any(digit not in domain for row in grid for cell in row for digit in cell):
        return False

    constraint_types = {c.type for c in puzzle.constraints}
    rows = grid if "rows-distinct" in constraint_types else []
    columns = (
        [[grid[row][col] for row in range(size)] for col in range(size)]
        if "cols-distinct" in constraint_types
        else []
    )
    regions = _regions(puzzle, size, grid)
    if any(not _is_permutation(group, domain) for group in (*rows, *columns, *regions)):
        return False

    for given in puzzle.givens:
        row, col = _row_col(given.address)
        if grid[row - 1][col - 1] != (given.digit,):
            return False
    return True


def _is_permutation(group: list[Cell], domain: frozenset[int]) -> bool:
    """`True` when `group`'s cells, flattened to individual digits (an
    S-cell's rendered pair contributing both), hold each of `domain`'s digits
    exactly once."""
    digits = [digit for cell in group for digit in cell]
    return len(digits) == len(domain) and frozenset(digits) == domain


def _parse_grid(rendered: str, size: int) -> list[list[Cell]] | None:
    """The rendered box-drawing grid, read back into a `size`x`size` array of
    cells, against `grid_text.py`'s named line/token contract:
    `grid_text.line_count(size)` total lines, cell tokens on
    `grid_text.cell_line_indices(size)`. Each cell token is either a bare
    digit or a Schrödinger S-cell pair `{a b}` (`grid_text.format_cell`);
    `grid_text.CELL_PATTERN` matches the pair whole
    so its two digits are never mistaken for two separate cells. `None` when
    the text doesn't have that many lines, or a cell line doesn't hold
    exactly `size` cell tokens — a shape mismatch, including a `render()`
    layout drift from this contract, is a validation failure, not a crash."""
    lines = [line for line in rendered.split("\n") if line]
    if len(lines) != grid_text.line_count(size):
        return None
    grid = []
    for index in grid_text.cell_line_indices(size):
        line = lines[index]
        cells = [
            grid_text.parse_cell(match)
            for match in grid_text.CELL_PATTERN.finditer(line)
        ]
        if len(cells) != size:
            return None
        grid.append(cells)
    return grid


def _regions(puzzle: Puzzle, size: int, grid: list[list[Cell]]) -> list[list[Cell]]:
    """No `regions-distinct` constraint means no permutation groups to check
    beyond rows/columns — the resolver's own no-regions fallback (one region
    covering the whole board) is a render-only convenience the solver never
    enforced, not a real group to validate."""
    has_regions = any(c.type == "regions-distinct" for c in puzzle.constraints)
    if not has_regions:
        return []
    region_map = region_map_for_constraints(puzzle.constraints, size)
    return [[grid[row - 1][col - 1] for row, col in group] for group in region_map]
