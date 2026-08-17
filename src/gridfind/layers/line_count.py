"""The `line-count-distinct` layer."""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine
from gridfind.layers._base import emit_distinct_count, flatten_slots, grid_content
from gridfind.layers.distinct import cols


@dataclass
class LineCountDistinct:
    """somedoku's rule: row *n* and column *n* each hold exactly *n* distinct
    digits, repeats allowed (ADR-0017). Rides on `board`'s `grid` structure
    exactly like `rows-distinct`/`cols-distinct` — registers nothing new in
    phase 1, only emits in phase 2.

    Counts distinct digits, not cells: feeds each line's flattened content
    slots into the distinct-count rule, so an S-cell's two digits both count
    toward the line's total, the same as `rows-distinct`'s is_S-gated house
    rule treats them. A non-S-cell's second slot sits on its own sentinel,
    always above every real digit, so it never matches a digit in
    `board.values` and drops out of the count on its own — no `s_blind`
    flag needed, this layer counts over whole content slots like
    `regions-distinct` does.
    """

    name: str = "line-count-distinct"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        grid = grid_content(engine)
        for row_index, row in enumerate(grid, start=1):
            label = f"row{row_index}"
            emit_distinct_count(
                engine, flatten_slots(row), target=row_index, label=label
            )
        for col_index, col in enumerate(cols(grid), start=1):
            label = f"col{col_index}"
            emit_distinct_count(
                engine, flatten_slots(col), target=col_index, label=label
            )
