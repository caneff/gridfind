"""The `line-count-distinct` layer."""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine, sole
from gridfind.layers._base import emit_distinct_count, grid_content
from gridfind.layers.distinct import cols


@dataclass
class LineCountDistinct:
    """somedoku's rule: row *n* and column *n* each hold exactly *n* distinct
    digits, repeats allowed (ADR-0017). Rides on `board`'s `grid` structure
    exactly like `rows-distinct`/`cols-distinct` — registers nothing new in
    phase 1, only emits in phase 2.
    """

    name: str = "line-count-distinct"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        grid = grid_content(engine)
        for row_index, row in enumerate(grid, start=1):
            cells = [sole(content) for content in row]
            label = f"row{row_index}"
            emit_distinct_count(engine, cells, target=row_index, label=label)
        for col_index, col in enumerate(cols(grid), start=1):
            cells = [sole(content) for content in col]
            label = f"col{col_index}"
            emit_distinct_count(engine, cells, target=col_index, label=label)
