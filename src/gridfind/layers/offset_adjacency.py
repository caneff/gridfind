"""`OffsetAdjacency`: cells a fixed set of grid offsets apart hold different
digits.

Anti-knight ("no two cells a chess-knight's hop apart share a digit") and
anti-king (the same for a king's step) are one rule over two offset lists.
Each is an `OffsetAdjacency` instance built with its own offsets; the layer
reads the directional stepper off `engine.cell_geometry` (ADR-0004) and, for
each cell and each of its offsets, emits a digit-disjointness rule against the
in-space target. `CellGeometry` never learns the words "knight" or "king" —
the offsets live here, owned by the layer.

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
    emits in phase 2.

    Reads each cell's real digit slots through `Engine.real_digit_values`
    (ADR-0019 dec 6, the guard-dropping unwrap of `real_digit_slots`) into one
    `add_all_different` per pair — the same digit-mode read `cage.py`'s
    digits-distinct mode folds a whole group through, here over just the two
    cells an offset relates. A non-S-cell's sentinel second slot never
    collides (`real_digit_slots`'s docstring), so no `is_s` branch is needed;
    no `s_blind` flag, so this composes with a widening (Schrödinger) layer
    instead of `build_stack` refusing the combination."""

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
                        engine.model.add_all_different(
                            engine.real_digit_values(cell)
                            + engine.real_digit_values(target)
                        )
