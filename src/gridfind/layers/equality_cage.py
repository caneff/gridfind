"""The `equality-cage` layer: even/low/high balance, all digits distinct.

An equality cage forces its cells to hold equal counts of even and odd
digits, and equal counts of low and high digits, over `N = len(cells)`.
Uniqueness is not this layer's job: an equality cage is a `cage`
(`distinct-over: "digit"`) composed alongside this layer over the same cells,
exactly as a killer cage composes `cage` with `group-sum` (ADR-0009) — this
layer states no distinctness rule and reads no `distinct-over` param.

One stateless `equality-cage` instance pulls every such constraint via
`constraints_of` and emits, per clue: `#even == N/2` (odd follows from the
same count), and `#low == N/2` **and** `#high == N/2`. `N` must be even — a
cage can never balance in halves otherwise — an odd cell count raises
`MalformedPuzzleError` at emit. Arithmetic reads each cell through
`Engine.value_expr` (ADR-0009), so a doubler or S-cell inside the cage is
classified by its value (parity and rank of `2·digit` / `s_value`), not its
raw digit — the same value channel a killer `group-sum` reads.

Low and high split the board's digit range at its midpoint: with `D =
len(board.values)` and `half = D // 2`, the `half` smallest values are low
and the `half` largest are high. For odd `D` (a 9-digit board) that leaves
exactly one value — the true middle, 5 on a 9-board — in neither half; for
even `D` (a 10-digit Schrödinger 0-9 board) the two halves partition every
value with no leftover. Forcing both halves to their own `N/2` count makes
that middle value's exclusion emergent: a cage cell holding it contributes
to neither count, so the two `N/2` totals can only be met by every other
cell — no explicit domain bar is ever stated. A modifier's widened value
(e.g. a doubled 5 -> 10) is classified the same way, against the same fixed
threshold, even though it falls outside the board's own digit range.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.cell_geometry import BoardShape
from gridfind.engine import Engine, MalformedPuzzleError


def _low_high_thresholds(board: BoardShape) -> tuple[int, int]:
    """The inclusive `(low_max, high_min)` bounds splitting the board's digit
    range at its midpoint: a value at or below `low_max` is low, at or above
    `high_min` is high. `half = D // 2` values fall in each half regardless
    of where the range starts, so a value halfway between them (the one odd-D
    leaves over) satisfies neither bound."""
    values = board.values
    d = len(values)
    half = d // 2
    start = values[0]
    return start + half - 1, start + d - half


@dataclass
class EqualityCage:
    name: str = "equality-cage"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            addresses = engine.cell_addresses(clue)
            self._emit_clue(engine, addresses)

    def _emit_clue(self, engine: Engine, addresses: list[str]) -> None:
        n = len(addresses)
        if n % 2 != 0:
            msg = (
                f"equality-cage needs an even cell count to balance in halves, got {n}"
            )
            raise MalformedPuzzleError(msg)
        half = n // 2
        low_max, high_min = _low_high_thresholds(engine.board)

        is_even, is_low, is_high = [], [], []
        for address in addresses:
            value = engine.value_expr(address)
            label = f"{self.name}.{address}"

            remainder = engine.model.new_int_var(0, 1, f"{label}.parity")
            engine.model.add_modulo_equality(remainder, value, 2)
            even = engine.model.new_bool_var(f"{label}.even")
            engine.model.add(remainder == 0).only_enforce_if(even)
            engine.model.add(remainder == 1).only_enforce_if(even.negated())
            is_even.append(even)

            low = engine.model.new_bool_var(f"{label}.low")
            engine.model.add(value <= low_max).only_enforce_if(low)
            engine.model.add(value > low_max).only_enforce_if(low.negated())
            is_low.append(low)

            high = engine.model.new_bool_var(f"{label}.high")
            engine.model.add(value >= high_min).only_enforce_if(high)
            engine.model.add(value < high_min).only_enforce_if(high.negated())
            is_high.append(high)

        engine.model.add(sum(is_even) == half)
        engine.model.add(sum(is_low) == half)
        engine.model.add(sum(is_high) == half)
