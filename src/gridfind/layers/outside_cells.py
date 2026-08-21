"""The `outside-cells` layer: the border-ring cells it registers.

Mirrors `board` for cells off the grid (CONTEXT.md, "outside cell"): the sole
creator of an outside cell, so two clues that both name the same border
address bind the one cell `add_cell` first creates rather than each
registering — and silently orphaning — their own (the `add_cell`
replace-orphan hazard). It never emits a rule of its own; a decoration or
clue layer that names an outside cell's address reads it exactly like any
grid cell, through the engine's ordinary content/value seams.

Reads every constraint's own `cells` addresses, generic across clue types
rather than a Numbered-Rooms-specific field, so the next outside clue (an
X-sum, a little-killer) reuses this layer with no second creator of its own.
Compulsory in `build_stack.build_stack`, always present alongside `board`,
so a decoration layer's `emit` (phase 2) can always assume a border address
it was handed is already a live cell.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.cell_geometry import parse_address
from gridfind.engine import Engine


def _is_outside(address: str, size: int) -> bool:
    """`True` when `address` names a position off the `size`x`size` grid —
    a border row or column of `0` or `size + 1`, the padded outside-cell
    addressing an escape-the-grid frame peel produces."""
    row, col = parse_address(address)
    return not (1 <= row <= size and 1 <= col <= size)


@dataclass
class OutsideCells:
    name: str = "outside-cells"
    depends_on: tuple[str, ...] = ()

    def register(self, engine: Engine) -> None:
        board = engine.board
        for constraint in engine.constraints:
            cells = constraint.params.get("cells")
            if not isinstance(cells, list):
                continue
            for address in cells:
                if not isinstance(address, str):
                    continue
                if address in engine.cells:
                    continue
                if _is_outside(address, board.size):
                    engine.add_cell(
                        address, low=board.values.start, high=board.values[-1]
                    )
                    engine.restrict(address, board.values)

    def emit(self, engine: Engine) -> None:
        pass
