"""The `numbered-rooms` layer: SudokuMaker's Numbered Rooms escape-the-grid
clue.

An outside cell governs the six inner cells of its own row or column, read
outward-to-inward from the clue: the near cell's placed digit `N` names a
1-based position on that line, and the outside cell must hold the digit the
line holds at that `N`th position — `outside == line[N - 1]`, the same
element/involution primitive `layers.indexing` already realizes for the 159
self-reference clue (ADR-0019, the shared `add_element` seam), reused here
rather than reimplemented. Two things differ from `indexing`'s use of the
seam: the index selects into the clue's own ordered tail (never the
control's own row/column), and the target is the outside cell's placed digit
(a variable) rather than a fixed row/column number — `add_element` already
accepts a variable target, so no second primitive is needed.

Reads the placed digit (`Engine.d0`), never `value_expr` (ADR-0009's
digit-read exception, mirroring `layers.indexing`) — "digit `N` sits at the
near cell" is a statement about the placed symbol, so a doubler anywhere in
the line is transparent to the rule.

`clue.params["cells"]` is `[outside, *line]`: index 0 the outside cell
(`outside_cells.OutsideCells` is the sole creator of that address, seeded
into every stack), the rest the line's cells ordered from the clue inward —
`line[0]` is the near cell whose own digit names the position.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.engine import Engine


def _emit_numbered_rooms_group(engine: Engine, outside: str, line: list[str]) -> None:
    variables = [engine.d0(address) for address in line]
    index = engine.d0(line[0]) - 1
    target = engine.d0(outside)
    engine.model.add_element(index, variables, target)


@dataclass
class NumberedRooms:
    """SudokuMaker's Numbered Rooms clue: an outside cell holds the digit its
    row/column's near-to-far line holds at the position the near cell's own
    digit names."""

    name: str = "numbered-rooms"
    depends_on: tuple[str, ...] = ("board", "outside-cells")

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            cells = cast("list[str]", clue.params["cells"])
            outside, line = cells[0], cells[1:]
            _emit_numbered_rooms_group(engine, outside, line)
