"""The general modifier-placement layer: `is_modifier`, one-per-house,
distinct-digit transversal (spec #232 decision #222, issue #234).

Registers a per-cell free boolean `is_modifier` and states the placement
rule every discovered-modifier puzzle shares: exactly one modifier per row,
per column, and per box, and the modified cells' digits are all-different (a
distinct-digit transversal read via `d0` — well-defined for a plain cell and
an S-cell alike, so composing with `schrodinger` costs nothing extra: no
guard against a cell being both is needed, forbidding it would only add a
constraint). "All-different" is capped at-most-once per digit, not a
bijection with `board.values` — `schrodinger` always widens `values` past
`board.size`, and the one-per-house rule fixes the modifier count at exactly
`board.size`, so a bijection would make every composed board infeasible. No
value change lives here — placement only. A future modifier type (a
doubler) reuses this layer and supplies only its own value fold; nothing
here is doubler-specific.

Unlike `is_s` (which `schrodinger` derives from content shape, and which
`distinct`'s counting rule picks up on its own), nothing else makes a cell a
modifier: a modifier adds no slot and frees no digit, so nothing but the
puzzle's own arithmetic would ever pressure a cell into it — and that
pressure doesn't exist yet (a value fold is a future modifier type's job).
So this layer states its placement rule outright in `emit`, rather than
leaving it to emerge the way `schrodinger` leaves the S-cell count to
`distinct`.

Reuses `distinct`'s `rows`/`cols`/`regions` partition functions to group the
board's own cell addresses (the `grid` structure `board` registers) — the
same partitions `rows-distinct`/`cols-distinct`/`regions-distinct` cut over
cell content, run here over cell addresses instead. `regions` is the classic
box tiling (issue #77); a board size with no box convention refuses there,
not here (issue #79 ruling).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.layers.distinct import cols, regions, rows

_HOUSE_PARTITIONS = (rows, cols, regions)


@dataclass
class ModifierPlacement:
    name: str = "modifier-placement"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        is_modifier = {
            address: engine.model.new_bool_var(f"{address}.is_modifier")
            for address in engine.cells
        }
        engine.register_structure("is_modifier", is_modifier)

    def emit(self, engine: Engine) -> None:
        is_modifier = cast(
            "dict[str, cp_model.IntVar]", engine.structures["is_modifier"]
        )
        grid = cast("list[list[str]]", engine.structures["grid"])
        for partition in _HOUSE_PARTITIONS:
            for group in partition(grid):
                addresses = list(group)
                engine.model.add(
                    sum(is_modifier[address] for address in addresses) == 1
                )
        self._emit_transversal(engine, is_modifier)

    def _emit_transversal(
        self, engine: Engine, is_modifier: dict[str, cp_model.IntVar]
    ) -> None:
        """Rule: the modified cells' digits are all-different — a transversal
        reading each modified cell's `d0`. For each digit, `holds` reifies
        "this cell is a modifier holding this digit"; at most one cell may,
        so no two modifiers ever share a digit — true all-different, not a
        bijection with `board.values`. `<= 1`, not `== 1`: a bijection only
        holds when `len(values) == board.size`, and `schrodinger` always
        widens `values` past `size`, so an `== 1` count would demand more
        modifiers than the one-per-house rule ever places, making every
        composed board unconditionally infeasible.
        """
        for digit in engine.board.values:
            holds = []
            for address in engine.cells:
                is_digit = engine.reify_holds(
                    [engine.d0(address)], digit, label=f"{self.name}.{address}"
                )[0]
                holds_digit = engine.model.new_bool_var(
                    f"{self.name}.{address}.at{digit}"
                )
                engine.model.add_min_equality(
                    holds_digit, [is_modifier[address], is_digit]
                )
                holds.append(holds_digit)
            engine.model.add(sum(holds) <= 1)
