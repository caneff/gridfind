"""The modifier layers: `ModifierPlacement` (`is_modifier`, one-per-house,
distinct-digit transversal) and `Modifier`, the shared base every concrete
modifier type (`Doubler` and its siblings) composes it through.

`ModifierPlacement` registers a per-cell free boolean `is_modifier` and
states the placement rule every discovered-modifier puzzle shares: exactly
one modifier per row, per column, and per box, and the modified cells'
digits are all-different (a distinct-digit transversal over every real digit
a cell contributes — `d0` for a plain cell, and an S-cell's `d1` too, since a
doubled S-cell doubles both of its digits). Composing with `schrodinger`
needs no guard against a cell being both modifier and S-cell: both slots come
from `engine.real_digit_slots`, the one place a non-S-cell's `d1` sentinel is
explained, so it never enters the count.
"All-different" is capped at-most-once per digit, not a bijection with
`board.values` — `schrodinger` always widens `values` past `board.size`, and
the one-per-house rule fixes the modifier count at exactly `board.size`, so a
bijection would make every composed board infeasible. No value change lives
here — placement only. `Modifier`, below, owns the value fold; each concrete
supplies only its own value expression and bounds (ADR-0016).

Unlike `is_s` (which `schrodinger` derives from content shape, and which
`distinct`'s counting rule picks up on its own), nothing else makes a cell a
modifier: a modifier adds no slot and frees no digit, so nothing but the
puzzle's own arithmetic would ever pressure a cell into it — and that
pressure doesn't exist yet (a value fold is a future modifier type's job).
So this layer states its placement rule outright in `emit`, rather than
leaving it to emerge the way `schrodinger` leaves the S-cell count to
`distinct`.

Reuses `distinct`'s `rows`/`cols`/`regions` partition functions to group the
board's own cell addresses (`engine.cell_geometry.grid`, ADR-0004) — the
same partitions `rows-distinct`/`cols-distinct`/`regions-distinct` cut over
cell content, run here over cell addresses instead. `regions` is the classic
box tiling; a board size with no box convention refuses there,
not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from gridfind.engine import Engine, GridfindError
from gridfind.layers.distinct import cols, regions, rows

_HOUSE_PARTITIONS = (rows, cols, regions)


@dataclass
class ModifierPlacement:
    """Places exactly one discovered modifier per row, column, and box, and
    forces the modified cells' digits to be a distinct-digit transversal.

    Satisfies the `Layer` protocol (`name`, `depends_on`) so it can compose
    directly into a stack on its own — `modifier_test.py` builds
    `[GridCells(), ModifierPlacement()]` to pin `is_modifier` in isolation,
    and one test relies on `depends_on` to prove the missing-`board` guard
    fires. Production never does this: `ModifierPlacement` is deliberately
    absent from `LAYER_REGISTRY` (ADR-0016, decision #222) — a puzzle only
    reaches it through `Modifier`'s `_placement` composition below (`Doubler`,
    `ConstantModifier`), never directly.
    """

    name: str = "modifier-placement"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        is_modifier = {
            address: engine.model.new_bool_var(f"{address}.is_modifier")
            for address in engine.cells
        }
        engine.register_structure("is_modifier", is_modifier)

    def emit(self, engine: Engine) -> None:
        is_modifier = engine.is_modifier()
        if is_modifier is None:
            raise GridfindError("is_modifier missing — register never ran")
        grid = engine.cell_geometry.grid
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
        over every real digit a modified cell contributes. A doubled S-cell
        holds two digits and doubles both (its value is `2·(d0+d1)`, ADR-0010),
        so both slots enter the count; a plain cell contributes only `d0`. For
        each digit, `holds` reifies "this cell is a modifier holding this digit
        in some slot"; at most one cell may, so no two modifiers ever share a
        doubled digit — true all-different, not a bijection with `board.values`.

        Reading both slots needs no `is_s` gate: `engine.real_digit_slots` is
        the one place the sentinel invariant lives, so its slots feed
        `reify_holds` directly and a non-S-cell's second slot contributes
        nothing on its own. `d0 < d1` keeps an S-cell's two slots distinct, so
        a single cell never collides with itself.

        `<= 1`, not `== 1`: a bijection only holds when `len(values) ==
        board.size`, and `schrodinger` always widens `values` past `size`, so
        an `== 1` count would demand more modifiers than the one-per-house rule
        ever places, making every composed board unconditionally infeasible.
        """
        for digit in engine.board.values:
            holds = []
            for address in engine.cells:
                slots = engine.real_digit_values(address)
                slot_holds = engine.reify_holds(
                    slots, digit, label=f"{self.name}.{address}"
                )
                is_digit = engine.model.new_bool_var(f"{self.name}.{address}.is{digit}")
                engine.model.add_max_equality(is_digit, slot_holds)
                holds_digit = engine.model.new_bool_var(
                    f"{self.name}.{address}.at{digit}"
                )
                engine.model.add_min_equality(
                    holds_digit, [is_modifier[address], is_digit]
                )
                holds.append(holds_digit)
            engine.model.add(sum(holds) <= 1)


@dataclass
class Modifier:
    """The shared base every discovered-modifier type composes: registers
    `modifier_type` and each cell's `modifier_value` on top of
    `ModifierPlacement`'s unchanged placement rule (one-per-house, the
    distinct-digit transversal). A concrete supplies exactly two hooks —
    `value_when_modified`, the expression a modified cell's value takes over
    its `underlying` value, and `modified_bounds`, that expression's integer
    range given the underlying value's own `(low, high)` — and nothing else;
    the value-fold plumbing (the free/discovered branch wiring, the IntVar
    sizing, the `modifier_type` registration) lives here once.

    `modifier_value` is sized to cover both branches: the free branch stays
    within the underlying value's own `(low, high)`, the discovered branch
    within `modified_bounds(low, high)`, so the variable's domain spans their
    union rather than assuming either branch is the tighter one.
    """

    name: str
    depends_on: tuple[str, ...] = ("board",)
    _placement: ModifierPlacement = field(default_factory=ModifierPlacement, repr=False)

    def value_when_modified(
        self, underlying: cp_model.LinearExprT
    ) -> cp_model.LinearExprT:
        """The expression a modified cell's value takes, over its `underlying`
        value beneath the modifier. Every concrete supplies its own."""
        raise NotImplementedError

    def modified_bounds(self, low: int, high: int) -> tuple[int, int]:
        """`value_when_modified`'s integer range given the underlying value's
        own `(low, high)`, so the base can size `modifier_value`'s domain to
        cover both branches. Every concrete supplies its own."""
        raise NotImplementedError

    def register(self, engine: Engine) -> None:
        # Register the value structures in phase 1, like schrodinger's
        # `s_value`, so every phase-2 reader (a killer `group-sum`, a
        # values-distinct `cage`) sees `modifier_value` no matter its own emit
        # order — a decoded link synthesizes a modifier constraint last, so a
        # phase-2 registration would arrive after those readers had already run.
        self._placement.register(engine)
        engine.register_structure(
            "modifier_type", dict.fromkeys(engine.cells, self.name)
        )
        is_modifier = engine.is_modifier()
        if is_modifier is None:
            raise GridfindError("is_modifier missing — register never ran")
        modifier_value: dict[str, cp_model.IntVar] = {}
        for address in engine.cells:
            # The value beneath the modifier — the cell's `base_value`, which
            # is its combined `s_value` for an S-cell and its digit otherwise
            # — so a concrete's fold never has to know a schrödinger layer
            # sits under it.
            underlying = engine.base_value(address)
            domain = underlying.proto.domain
            low, high = min(domain), max(domain)
            modified_low, modified_high = self.modified_bounds(low, high)
            value = engine.model.new_int_var(
                min(low, modified_low),
                max(high, modified_high),
                f"{address}.modifier_value",
            )
            engine.model.add(value == underlying).only_enforce_if(
                is_modifier[address].negated()
            )
            engine.model.add(
                value == self.value_when_modified(underlying)
            ).only_enforce_if(is_modifier[address])
            modifier_value[address] = value
        engine.register_structure("modifier_value", modifier_value)

    def emit(self, engine: Engine) -> None:
        self._placement.emit(engine)
