"""The `cage` layer: no-repeats over a named cell set, no cover pressure
(issue #157, spec #156 decision #150).

A cage clue names a set of cells and forbids a digit repeat among them —
unlike a region (`rows-distinct`, `cols-distinct`, `regions-distinct`), a
cage does not have to cover the whole digit domain, so a 7-cell cage on a
9-digit board is legal. One stateless `cage` instance pulls every such
constraint via `constraints_of` and emits one no-repeats rule per clue,
structured like `pair-sum` (a clue-looping layer), not like the
partition-driven `DistinctOverGroups` — no shared base with it.

The rule is a single `add_all_different` over the cage's is_S-gated slots,
read through the plural `contents()` seam (the same slot-gathering
`emit_house` uses for the cover rule): with no `schrodinger` layer, every
cell's content is width 1, so this is the identical plain `add_all_different`
`DistinctOverGroups` already emits with no `schrodinger` layer present. With
`schrodinger` present, the rule runs over both of a cage cell's slots — its
`d1` sentinel keeps a non-S cell's second slot out of the way, and an S-cell's
two real digits are both bound into the no-repeats set. Unlike `emit_house`,
this states no per-digit count, so it adds no cover pressure and never forces
a cell to become an S-cell.

An optional `name` param is accepted and reserved for future killer keying;
unread today.

A killer sum (issue #196, made S-aware by issue #235): an optional `value`
param, when present and `> 0`, additionally emits `sum(cells) == value` —
each cell contributing its one digit, or, on a cell an S-cell pin has
widened, both of its digits. The refusal a killer sum used to raise the
moment an S-cell was possible ("not Schrödinger-ready yet") is retired: the
per-cell contribution is gated on `is_s` (`_cage_sum_term`), the same
structure-registry fact the no-repeats half above already tolerates the
absence of, so a cage with no `schrodinger` layer in the stack keeps
summing each cell's sole content variable directly, byte-identical to
before. Absent `value` or `value == 0` (SudokuMaker's own no-sum cage) stays
region-only, exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine


def _cage_sum_term(
    engine: Engine, address: str, is_s: dict[str, cp_model.IntVar] | None
) -> cp_model.IntVar | cp_model.LinearExprT:
    """This cage cell's contribution to a killer sum: its one digit, or, once
    an S-cell pin has widened it, both — reified on `is_s` since which case
    applies is a solve-time fact, not something `emit` can branch on
    directly. A cell `schrodinger` never widened stays a plain content read,
    matching the pre-#235 model exactly."""
    contents = engine.contents(address)
    if len(contents) == 1:
        return contents[0]
    d0, d1 = contents
    s = cast("dict[str, cp_model.IntVar]", is_s)[address]
    board = engine.board
    term = engine.model.new_int_var(
        min(board.values), 2 * max(board.values), f"{address}.cage-sum-term"
    )
    engine.model.add(term == d0 + d1).only_enforce_if(s)
    engine.model.add(term == d0).only_enforce_if(s.negated())
    return term


@dataclass
class Cage:
    name: str = "cage"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        is_s = cast("dict[str, cp_model.IntVar] | None", engine.structures.get("is_s"))
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — narrow to this
            # clue's shape: the cage's cells, and an optional killer sum.
            # `name`, if present, is reserved and unread.
            addresses = cast("list[str]", clue.params["cells"])
            slots = [slot for address in addresses for slot in engine.contents(address)]
            engine.model.add_all_different(slots)
            value = clue.params.get("value")
            if value:
                total = cast("int", value)
                terms = [_cage_sum_term(engine, address, is_s) for address in addresses]
                engine.model.add(sum(terms) == total)
