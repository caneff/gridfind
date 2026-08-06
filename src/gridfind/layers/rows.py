"""The `rows-distinct` layer."""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine
from gridfind.layers._base import grid_vars


@dataclass
class RowsDistinct:
    """The first rule-emitting layer: each row's cells are all different
    (spec #4, decision 7). Rides on `board`'s `grid` structure — it
    registers nothing new in phase 1 and only emits rules in phase 2.
    """

    name: str = "rows-distinct"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for row in grid_vars(engine):
            engine.model.add_all_different(row)
