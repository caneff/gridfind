"""The engine spine: cells, the structure registry, and the two-phase build.

Knows no puzzle concepts and no geometry (spec #4, decision 31) — a layer
such as `board` supplies both.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from ortools.sat.python import cp_model

# The engine->layer contract's named surface (issue #28, ADR-0001). Layers code
# against these; everything else in the module is implementation detail.
__all__ = [
    "Cell",
    "Engine",
    "GridfindError",
    "Layer",
    "MissingDependencyError",
    "build_engine",
]


class GridfindError(Exception):
    """Base for engine-refusal errors."""


class MissingDependencyError(GridfindError):
    """A layer's declared dependency is not present in the stack."""


@dataclass
class Cell:
    """The atom. `content` is its ordered sequence of integer variables."""

    name: str
    content: list[cp_model.IntVar]


class Record(Protocol):
    """One variant's data, riding on the engine for a layer to turn into rules.

    A record pairs a `type` — the layer that handles it — with `params`, that
    variant's own settings: a killer cage's cells and target sum, a thermo's
    path. A layer pulls every record of its type with `records_of` and loops
    them, so one stateless layer serves a puzzle's many cages (issue #65).

    `params` is the open JSON boundary (spec #45), so its values are `object` —
    a layer narrows each to the shape it expects.

    The engine stays puzzle-agnostic (spec #4, decision 31): it knows this
    read-only view — `type` and `params` — never the `Variant` a record is. A
    layer reads a record; it never writes one back.
    """

    @property
    def type(self) -> str: ...

    @property
    def params(self) -> dict[str, object]: ...


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
    records: tuple[Record, ...] = ()

    def records_of(self, kind: str) -> list[Record]:
        """A data-bearing layer pulls its own records by type — the accessor
        beside the `cells` and `structures` a layer already reaches into."""
        return [record for record in self.records if record.type == kind]

    def add_cell(self, name: str, *, low: int, high: int, width: int = 1) -> Cell:
        content = [
            self.model.new_int_var(low, high, f"{name}.{i}") for i in range(width)
        ]
        cell = Cell(name=name, content=content)
        self.cells[name] = cell
        return cell

    def register_structure(self, name: str, value: object) -> None:
        self.structures[name] = value

    def value(self, solver: cp_model.CpSolver, name: str) -> int:
        """A cell's placed value after a solve — the one home for reading
        cell-content width (issue #72). Relocates today's width-1 behaviour
        unchanged; a width-2 (S-cell) read is `schrodinger`'s to design, so
        this raises rather than silently taking `content[0]`."""
        content = self._cell(name).content
        if len(content) != 1:
            msg = f"cell {name!r} has width {len(content)}, expected 1"
            raise ValueError(msg)
        return solver.value(content[0])

    def restrict(self, name: str, digits: Iterable[int]) -> None:
        """Pin a cell to a set of digits — a given/place is a singleton set,
        a candidate a subset, both one operation (issue #72). Each digit is
        checked against the cell's own declared domain by membership, not a
        min/max range — a range would admit holes in a non-contiguous domain
        like {1, 3, 5} — and an unknown address raises."""
        var = self._cell(name).content[0]
        domain = cp_model.Domain.from_flat_intervals(var.proto.domain)
        allowed = sorted(set(digits))
        for digit in allowed:
            if not domain.contains(digit):
                msg = f"digit {digit} out of range {domain} for cell {name!r}"
                raise ValueError(msg)
        self.model.add_allowed_assignments([var], [(digit,) for digit in allowed])

    def _cell(self, name: str) -> Cell:
        cell = self.cells.get(name)
        if cell is None:
            msg = f"address {name!r} is off the board"
            raise ValueError(msg)
        return cell


def build_engine(layers: list[Layer], records: tuple[Record, ...] = ()) -> Engine:
    """The two-phase build (spec #4, decision 10): order-insensitive.

    Phase 1 — every layer registers its cells and structures.
    Phase 2 — every layer emits its rules against the now-final structures.

    The puzzle's `records` ride on the engine so both phases can query them by
    type (issue #65) — available before phase 1, which is what lets a future
    Schrödinger-style layer widen named cells at register time.

    A layer's declared dependency is a validity check, not a build-order
    crutch: missing dependency refuses the build before either phase runs.
    """
    present = {layer.name for layer in layers}
    for layer in layers:
        for dep in layer.depends_on:
            if dep not in present:
                msg = f"layer {layer.name!r} requires {dep!r}, not in stack"
                raise MissingDependencyError(msg)

    engine = Engine(records=records)
    for layer in layers:
        layer.register(engine)
    for layer in layers:
        layer.emit(engine)
    return engine
