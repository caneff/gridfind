"""`OffsetAdjacency`: cells a fixed set of grid offsets apart hold different
digits.

Anti-knight ("no two cells a chess-knight's hop apart share a digit") and
anti-king (the same for a king's step) are one rule over two offset lists.
Each is an `OffsetAdjacency` instance built with its own offsets; the layer
reads the directional stepper off `engine.cell_geometry` (ADR-0004) and, for
each cell and each of its offsets, emits an inequality against the in-space
target. `CellGeometry` never learns the words "knight" or "king" — the offsets
live here, owned by the layer.

The stepper resolves an offset against the declared cell-address set, so an
offset that leaves the space yields no target and no rule — the cell-space
contract that lets off-grid cells (#399) extend the space later.

Each offset is emitted independently, so a cell and its target constrain each
other from both ends (a knight/king offset and its negation both appear). The
two directions state the same inequality; CP-SAT carries the duplicate for
free, and the alternative — deduping pairs — would buy nothing at these sizes.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine

# A knight's eight L-hops: two along one axis, one along the other.
KNIGHT_OFFSETS: tuple[tuple[int, int], ...] = (
    (-2, -1),
    (-2, 1),
    (-1, -2),
    (-1, 2),
    (1, -2),
    (1, 2),
    (2, -1),
    (2, 1),
)

# A king's eight neighbors: every orthogonal and diagonal step of one.
KING_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


@dataclass
class OffsetAdjacency:
    """Every pair of cells one of `offsets` apart holds different digits.
    Reads the grid and stepper off `board`'s geometry; registers nothing,
    emits in phase 2."""

    name: str
    offsets: tuple[tuple[int, int], ...]
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        geometry = engine.cell_geometry
        for row in geometry.grid:
            for cell in row:
                for delta_row, delta_col in self.offsets:
                    target = geometry.step(cell, delta_row, delta_col)
                    if target is not None:
                        engine.model.add(engine.content(cell) != engine.content(target))
