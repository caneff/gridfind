"""`OffsetAdjacency` and `OffsetValueGap`: cells a fixed set of grid offsets
apart hold, respectively, different digits or values more than one apart.

Anti-knight ("no two cells a chess-knight's hop apart share a digit") and
anti-king (the same for a king's step) are one rule over two offset lists.
Each is an `OffsetAdjacency` instance built with its own offsets. Nonconsecutive
("no two orthogonal neighbours differ by exactly 1", ADR-0019/#749) is the
same offset-walk shape over a different rule, so it is `OffsetValueGap`, a
sibling built with `ORTHOGONAL_OFFSETS`, rather than a mode flag bolted onto
`OffsetAdjacency`. Both layers read the directional stepper off
`engine.cell_geometry` (ADR-0004) through the one shared `offset_pairs`
generator below; only the rule each emits per pair differs. `CellGeometry`
never learns the words "knight", "king", or "orthogonal" — the offsets live
here, owned by the layers.

The stepper resolves an offset against the declared cell-address set, so an
offset that leaves the space yields no target and no rule — the cell-space
contract that lets off-grid cells (#399) extend the space later.

Each offset is emitted independently, so a cell and its target constrain each
other from both ends (a knight/king/orthogonal offset and its negation both
appear). The two directions state the same rule; CP-SAT carries the duplicate
for free, and the alternative — deduping pairs — would buy nothing at these
sizes.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from gridfind.engine import Engine
from gridfind.layers._base import abs_diff_var

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

ORTHOGONAL_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
)


def offset_pairs(
    engine: Engine, offsets: tuple[tuple[int, int], ...]
) -> Iterator[tuple[str, str]]:
    """Every `(cell, target)` pair the board yields for `offsets`: each cell of
    `engine.cell_geometry`'s grid against each of its offsets, skipping an
    offset that steps off the declared cell-address set. The one walk
    `OffsetAdjacency` and `OffsetValueGap` both drive, so a stepper change
    lands once (#749)."""
    geometry = engine.cell_geometry
    for row in geometry.grid:
        for cell in row:
            for delta_row, delta_col in offsets:
                target = geometry.step(cell, delta_row, delta_col)
                if target is not None:
                    yield cell, target


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
        for cell, target in offset_pairs(engine, self.offsets):
            engine.model.add_all_different(
                engine.real_digit_values(cell) + engine.real_digit_values(target)
            )


@dataclass
class OffsetValueGap:
    """Every pair of cells one of `offsets` apart holds values that differ by
    more than 1 — nonconsecutive's rule (#749). Reads the grid and stepper off
    `board`'s geometry via the shared `offset_pairs` walk; registers nothing,
    emits in phase 2.

    Value mode (ADR-0019 dec 2, whisper's mode): reads each cell through
    `Engine.value_expr`, a doubler's `2·d0` or a doubled S-cell's `2·s_value`
    in place of the bare digit, so a modifier composes without a special
    case. No `mode` argument — value mode only; a digit-mode ∀ read (no S-cell
    digit consecutive with any neighbour digit) is the named upgrade path if a
    digit-mode neighbour rule ever arrives. No `s_blind` flag, so this
    composes with a widening (Schrödinger) layer instead of `build_stack`
    refusing the combination. `abs_diff_var` (`_base.py`) mints the one aux
    var per pair the way `pair_difference.differs_by` does; pinning it `!= 1`
    is the negated-pair-difference shape with a fixed target of 1, applied to
    every walked pair instead of one named clue."""

    name: str
    offsets: tuple[tuple[int, int], ...]
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for cell, target in offset_pairs(engine, self.offsets):
            a = engine.value_expr(cell)
            b = engine.value_expr(target)
            gap = abs_diff_var(engine, a, b, suffix="gap")
            engine.model.add(gap != 1)
