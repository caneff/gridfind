"""The `clone` layer: SudokuMaker's clone clue (wire type `302`).

Reads digit mode: the cells of each group must hold equal digit **sets** —
digits only, never the modifier marking, so a cloned cell does not inherit its
source's doubler or constant (ADR-0019 dec 4). Reads each cell through
`Engine.real_digit_slots`, the gated digit read (dec 6), so the sentinel that
fills a singleton's second slot is never compared.

Set equality is exact per cell pair because a Schrödinger cell's two digits are
canonical ascending (`d0 < d1`, ADR-0019 dec 4): two cells hold the same digit
set when their real slots match slot for slot — `d0` always equal, the widths
(`is_s`) equal, and `d1` equal *only when the cell is really width 2*. That last
term is the gated one, enforced under its `real_digit_slots` guard. A group of
more than two cells chains consecutive pairs; equality is transitive, so the
chain closes the whole group.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from gridfind.engine import Engine


def _equate_digit_sets(engine: Engine, first: str, second: str) -> None:
    """Rule: `first` and `second` hold equal digit sets. Their real digit slots
    line up slot for slot (same layer stack, so same width): an ungated slot
    (`d0`) is equal unconditionally; a gated slot (`d1`) forces its guards equal
    — so the cells are S-cells together or neither — and its digits equal only
    when the slot is real."""
    for (digit_a, guard_a), (digit_b, guard_b) in zip(
        engine.real_digit_slots(first), engine.real_digit_slots(second), strict=True
    ):
        if guard_a is None or guard_b is None:
            engine.model.add(digit_a == digit_b)
        else:
            engine.model.add(guard_a == guard_b)
            engine.model.add(digit_a == digit_b).only_enforce_if(guard_a)


@dataclass
class Clone:
    """SudokuMaker's clone clue: within each group, every cell holds the same
    digit set as the next — digits only, no modifier marking carried."""

    name: str = "clone"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            cells = engine.cell_addresses(clue)
            for first, second in pairwise(cells):
                _equate_digit_sets(engine, first, second)
