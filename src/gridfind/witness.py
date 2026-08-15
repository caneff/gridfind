"""The found solve's witness: its per-cell content, and how it renders.

A `Witness` is what a `found` verdict carries: the
content sequence each cell holds, paired with the board shape that read them,
so a consumer lays the grid out without re-deriving addressing. Rendering it —
turning the assignment into a bordered text grid — is a self-contained concern
with no bearing on the found / broke / unknown decision, so it lives here beside
the dataclass rather than inside `verdict.py`.

`witness_validator.py` reads a rendered witness back independently and never
imports this module, on purpose: a renderer defect must not hide
behind the same code that produced the grid. Both sides do cite
`grid_text.py` — the named text-shape contract that keeps a
layout change here from silently drifting out from under the validator's
parse.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gridfind import grid_text
from gridfind.layers.regions import RegionMap

# A box-drawing glyph for a grid junction, keyed by which arms (up, down,
# left, right) meet there. An arm is present where the region changes across
# it or at the outer edge, so the glyph shows exactly the lines
# that meet — never a floating stub.
_JUNCTIONS = {
    (False, False, False, False): " ",
    (False, False, True, True): "─",
    (True, True, False, False): "│",
    (False, True, False, True): "┌",
    (False, True, True, False): "┐",
    (True, False, False, True): "└",
    (True, False, True, False): "┘",
    (True, True, False, True): "├",
    (True, True, True, False): "┤",
    (False, True, True, True): "┬",
    (True, False, True, True): "┴",
    (True, True, True, True): "┼",
}


# A witness's identity: its full per-cell content, keyed for dedup. The
# `assignment` entries hold each cell's digit sequence — a widened S-cell's
# ordered pair, every other cell's lone `d0` — so the Schrödinger indicator and
# second digit ride along wherever that layer widens a cell; the `modifiers`
# entries name every discovered doubler. Together they are the whole grid
# ADR-0015 makes the identity, nothing dropped. Two completions that share
# every `d0` are still distinct here when they place the S-cell differently or
# the doubler on another cell.
WitnessIdentity = tuple[
    tuple[tuple[str, tuple[int, ...]], ...], tuple[tuple[str, str], ...]
]


@dataclass(frozen=True)
class Witness:
    """A found solve's content sequence per cell, paired with the board shape
    that read them — self-describing, so a
    consumer lays the grid out without re-deriving addressing. `assignment`
    stays reachable directly for a caller that wants one cell, not a render.

    It is an *assignment*, not `values`: `Board.values` is the digit domain a
    cell may hold, and one word for both the offer and the choice reads badly
    three lines apart.

    A cell's tuple is a 1-tuple for a singleton, a 2-tuple `(a, b)`, `a < b`,
    for a Schrödinger S-cell (the `schrodinger` layer's content seam) — never the
    sentinel `contents()`/`values()` may
    also carry for an unsolved S-cell slot.

    `region_map` is the partition `render` borders against —
    always populated, never `None`: a board with no regions-distinct rule of
    its own still gets one region covering the whole board, so there is
    nothing to guess at render time.

    `modifiers` names every cell the solver discovered as a modifier —
    address to the puzzle's declared modifier type (`"doubler"`), populated
    from `is_modifier` exactly as `assignment` is from `is_s`. `assignment`
    still carries the digit, never the modifier's
    folded value — a given on a modified cell pins the digit, and the value
    derives from it at render/read time, not here. Empty on a puzzle with no
    modifier layer, never `None`."""

    grid: list[list[str]]
    assignment: dict[str, tuple[int, ...]]
    region_map: RegionMap
    modifiers: dict[str, str] = field(default_factory=dict)

    def __getitem__(self, address: str) -> tuple[int, ...]:
        return self.assignment[address]

    def __len__(self) -> int:
        return len(self.assignment)

    @property
    def identity(self) -> WitnessIdentity:
        """This witness's dedup key: `assignment` and `modifiers`, frozen into
        a hashable tuple. Both dicts iterate in `engine.cells` order, the same
        order for every witness in one enumeration, so equal content yields an
        equal key without sorting."""
        return tuple(self.assignment.items()), tuple(self.modifiers.items())

    def render(self) -> str:
        """The witness as text, bordered wherever two adjacent cells fall in
        different regions: junctions are resolved from the four
        lines meeting at each grid node, so a classic box partition draws the
        familiar 3x3 boxes and a jigsaw partition draws its own region
        borders through the same path.

        A singleton cell prints its bare digit; an S-cell prints its
        unordered pair `{a b}`, via
        `grid_text.format_cell` — the same token shape `witness_validator`
        parses back. Every cell is right-padded to the widest
        cell in the witness so columns stay aligned and the box banding
        survives whatever width an S-cell adds.
        """
        n = len(self.grid)
        region_id = {
            cell: index for index, group in enumerate(self.region_map) for cell in group
        }

        def region_at(row: int, col: int) -> int:
            return region_id[(row + 1, col + 1)]

        def wall(row: int, col: int) -> bool:
            return (
                col == 0 or col == n or region_at(row, col - 1) != region_at(row, col)
            )

        def seg(row: int, col: int) -> bool:
            return (
                row == 0 or row == n or region_at(row - 1, col) != region_at(row, col)
            )

        formatted = [
            [grid_text.format_cell(self.assignment[address]) for address in row]
            for row in self.grid
        ]
        width = max(len(cell) for row in formatted for cell in row)

        lines: list[str] = []
        for b in range(n + 1):
            border = ""
            for c in range(n + 1):
                arms = (
                    b > 0 and wall(b - 1, c),
                    b < n and wall(b, c),
                    c > 0 and seg(b, c - 1),
                    c < n and seg(b, c),
                )
                border += _JUNCTIONS[arms]
                if c < n:
                    border += ("─" if seg(b, c) else " ") * (width + 2)
            lines.append(border)
            if b < n:
                cells = "".join(
                    ("│" if wall(b, c) else " ") + f" {formatted[b][c].rjust(width)} "
                    for c in range(n)
                )
                lines.append(cells + ("│" if wall(b, n) else " "))
        return "\n".join(lines)
