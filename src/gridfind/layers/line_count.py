"""The `line-count-distinct` layer."""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine
from gridfind.layers._base import emit_distinct_count, grid_content


@dataclass
class LineCountDistinct:
    """somedoku's rule: row *n* holds exactly *n* distinct digits, repeats
    allowed (spec #4, decision 7 — line-count-distinct; issue #10). Rides on
    `board`'s `grid` structure exactly like `rows-distinct` — registers
    nothing new in phase 1, only emits in phase 2.
    """

    name: str = "line-count-distinct"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for row_index, row in enumerate(grid_content(engine), start=1):
            cells = [contents[0] for contents in row]
            label = f"row{row_index}"
            emit_distinct_count(engine, cells, target=row_index, label=label)
