"""The `cols-distinct` layer."""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine
from gridfind.layers._base import grid_vars


@dataclass
class ColsDistinct:
    """Mirror of `rows-distinct`: each column's cells are all different
    (spec #4, decision 7; issue #7). Also rides on `board`'s `grid`
    structure — registers nothing new in phase 1, only emits rules in
    phase 2.
    """

    name: str = "cols-distinct"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for col in zip(*grid_vars(engine), strict=True):
            engine.model.add_all_different(col)
