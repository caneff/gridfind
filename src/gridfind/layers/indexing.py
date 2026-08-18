"""The `indexing` layer: SudokuMaker's 159 self-referential clue.

A marked control cell's placed digit `V` names a **position** on its own
indexed line — its row for column-indexing, its column for row-indexing —
and the line's cell at that position must hold the control's own coordinate
on the other axis. Column-indexing: `(R,C)=V ⟺ (R,V)=C`. Row-indexing is the
transpose: `(R,C)=V ⟺ (V,C)=R`. The involution falls out of the per-cell
forward rule plus the board's own placement; no separate reverse constraint
is emitted.

One `add_element` per marked cell realizes it directly: `V-1` selects the
line's cell at that 0-based position, which must equal the coordinate —
native OR-Tools (ADR-0001), no reified either-or needed since `V` already
names the position. `clue.params["cells"]` may hold any number of marked
cells across any number of clues; each is independent.

Reads the placed digit (`Engine.d0`), never `value_expr` (ADR-0009's digit-
read exception, `CONTEXT.md`) — "digit `C` sits at the indexed cell" is a
statement about the placed symbol, and a doubler's folded value would make
its own match fail (`2C != C`) though `C` is plainly placed. A doubler on a
marked or indexed cell is therefore transparent to the rule, with no special
case: the read never reaches `value_expr` in the first place.

Scope: width-1 cells only — `d0` is a not-yet-widened
cell's sole slot and a widened S-cell's always-real first slot alike, so
this reads correctly for every width-1 puzzle without declaring `s_blind`.
Full S-cell membership (an S-cell counts as placing either digit, a control
indexes from both) and the index-0 refusal are a follow-on layer change, not
a rebuild — leaving `s_blind` undeclared here is what lets that follow-on
stack `indexing` over `schrodinger` without touching this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.cell_geometry import format_address, parse_address
from gridfind.engine import Engine


def _indexed_line(
    engine: Engine, row: int, col: int, axis: str
) -> list[cp_model.IntVar]:
    """The control cell's indexed line, in position order `1..N`: its own row
    (column-indexing reads across it) or its own column (row-indexing reads
    down it)."""
    size = engine.board.size
    if axis == "col":
        return [engine.d0(format_address(row, c)) for c in range(1, size + 1)]
    return [engine.d0(format_address(r, col)) for r in range(1, size + 1)]


def _emit_indexing_cell(engine: Engine, address: str, axis: str) -> None:
    row, col = parse_address(address)
    line = _indexed_line(engine, row, col, axis)
    coordinate = col if axis == "col" else row
    index = engine.d0(address) - 1
    engine.model.add_element(index, line, coordinate)


@dataclass
class Indexing:
    name: str = "indexing"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            axis = cast("str", clue.params["axis"])
            for address in engine.cell_addresses(clue):
                _emit_indexing_cell(engine, address, axis)
