"""The `indexing` layer: SudokuMaker's 159 self-referential clue.

A marked control cell's placed digit `V` names a **position** on its own
indexed line — its row for column-indexing, its column for row-indexing —
and the line's cell at that position must hold the control's own coordinate
on the other axis. Column-indexing: `(R,C)=V ⟺ (R,V)=C`. Row-indexing is the
transpose: `(R,C)=V ⟺ (V,C)=R`. The involution falls out of the per-cell
forward rule plus the board's own placement; no separate reverse constraint
is emitted.

`clue.params["cells"]` may hold any number of marked cells across any number
of clues; each is independent.

Reads the placed digit (`Engine.d0`/`Engine.contents`), never `value_expr`
(ADR-0009's digit-read exception, `CONTEXT.md`) — "digit `C` sits at the
indexed cell" is a statement about the placed symbol, and a doubler's folded
value would make its own match fail (`2C != C`) though `C` is plainly
placed. A doubler on a marked or indexed cell is therefore transparent to
the rule, with no special case: the read never reaches `value_expr` in the
first place.

Not `s_blind`: with no widening layer in the stack, a marked cell's `V` is
its sole slot and one `add_element` per marked cell realizes the rule
directly — `V-1` selects the line's cell at that 0-based position, which
must equal the coordinate, native OR-Tools (ADR-0001), no reified
either-or needed since `V` already names the position.

With a widening layer in the stack (`engine.is_s()` present), "digit `C`
sits at the indexed cell" widens to **membership** over the cell's content
slots (`C == d0` or, for an S-cell, `C == d1`) and a control **indexes from
every digit it holds** — an S-cell control holding `{a, b}` sends its
coordinate to both position `a` and position `b`. Realized per marked cell
as one implication per line position `p` and per control slot: "control
holds `p`" ⟹ "line cell at `p` holds the coordinate" (`engine.reify_holds`
+ `add_bool_or(...).only_enforce_if(...)`, the house-rule idiom). A
non-S-cell's second slot sits on its own sentinel, always above every real
digit (`schrodinger`), so it never matches a position or a coordinate and
drops out of both sides on its own — no explicit `is_s` gate needed, the
same reasoning `line_count.py`/`_base.emit_house` lean on.

Index 0 names no position, so a control may never hold it: enforced
directly as `d0(control) != 0`, which (with `schrodinger`'s `d0 < d1`
canonicalization) forbids the whole pair from holding 0. A control forced to
0 therefore has no digit ≥ 1 to index from, and the rule above never fires
for it — reading broke, not silently satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from gridfind.cell_geometry import format_address, parse_address
from gridfind.engine import Engine


def _line_addresses(engine: Engine, row: int, col: int, axis: str) -> list[str]:
    """The control cell's indexed line, in position order `1..N`: its own row
    (column-indexing reads across it) or its own column (row-indexing reads
    down it)."""
    size = engine.board.size
    if axis == "col":
        return [format_address(row, c) for c in range(1, size + 1)]
    return [format_address(r, col) for r in range(1, size + 1)]


def _emit_width1_indexing_cell(
    engine: Engine, address: str, row: int, col: int, axis: str
) -> None:
    line = [engine.d0(a) for a in _line_addresses(engine, row, col, axis)]
    coordinate = col if axis == "col" else row
    index = engine.d0(address) - 1
    engine.model.add_element(index, line, coordinate)


def _emit_s_aware_indexing_cell(
    engine: Engine, address: str, row: int, col: int, axis: str
) -> None:
    coordinate = col if axis == "col" else row
    control_content = engine.contents(address)
    engine.model.add(control_content[0] != 0)
    for position, target in enumerate(_line_addresses(engine, row, col, axis), start=1):
        control_holds = engine.reify_holds(
            control_content, position, f"{address}.holds{position}"
        )
        target_holds = engine.reify_holds(
            engine.contents(target),
            coordinate,
            f"{target}.holds{coordinate}.from.{address}",
        )
        for indicator in control_holds:
            engine.model.add_bool_or(target_holds).only_enforce_if(indicator)


def _emit_indexing_cell(engine: Engine, address: str, axis: str) -> None:
    row, col = parse_address(address)
    if engine.is_s() is None:
        _emit_width1_indexing_cell(engine, address, row, col, axis)
        return
    _emit_s_aware_indexing_cell(engine, address, row, col, axis)


@dataclass
class Indexing:
    """SudokuMaker's self-referential 159 clue: a marked control cell's digit
    names a position on its own line, which must hold the control's own
    coordinate on the other axis."""

    name: str = "indexing"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            axis = cast("str", clue.params["axis"])
            for address in engine.cell_addresses(clue):
                _emit_indexing_cell(engine, address, axis)
