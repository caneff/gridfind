"""The engine spine: cells, the structure registry, and the two-phase build.

Knows no puzzle concepts and no geometry (spec #4, decision 31) — a layer
such as `board` supplies both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ortools.sat.python import cp_model


class GridfindError(Exception):
    """Base for engine-refusal errors."""


class MissingDependencyError(GridfindError):
    """A layer's declared dependency is not present in the stack."""


@dataclass
class Cell:
    """The atom. `content` is its ordered sequence of integer variables."""

    name: str
    content: list[cp_model.IntVar]


class Layer(Protocol):
    """A composable, parameterized rule-family module."""

    name: str
    depends_on: tuple[str, ...]

    def register(self, engine: Engine) -> None:
        """Phase 1: register this layer's cells and structures."""

    def emit(self, engine: Engine) -> None:
        """Phase 2: emit this layer's rules against final structures."""


@dataclass
class Engine:
    """Holds the CP-SAT model, cell content, and the structure registry."""

    model: cp_model.CpModel = field(default_factory=cp_model.CpModel)
    cells: dict[str, Cell] = field(default_factory=dict)
    structures: dict[str, object] = field(default_factory=dict)

    def add_cell(self, name: str, *, low: int, high: int, width: int = 1) -> Cell:
        content = [
            self.model.new_int_var(low, high, f"{name}.{i}") for i in range(width)
        ]
        cell = Cell(name=name, content=content)
        self.cells[name] = cell
        return cell

    def register_structure(self, name: str, value: object) -> None:
        self.structures[name] = value


def build_engine(layers: list[Layer]) -> Engine:
    """The two-phase build (spec #4, decision 10): order-insensitive.

    Phase 1 — every layer registers its cells and structures.
    Phase 2 — every layer emits its rules against the now-final structures.

    A layer's declared dependency is a validity check, not a build-order
    crutch: missing dependency refuses the build before either phase runs.
    """
    present = {layer.name for layer in layers}
    for layer in layers:
        for dep in layer.depends_on:
            if dep not in present:
                msg = f"layer {layer.name!r} requires {dep!r}, not in stack"
                raise MissingDependencyError(msg)

    engine = Engine()
    for layer in layers:
        layer.register(engine)
    for layer in layers:
        layer.emit(engine)
    return engine
