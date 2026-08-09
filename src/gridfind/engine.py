"""The engine spine: cells, the structure registry, and the two-phase build.

Two channels reach a layer, and the line between them is whether the producer
and the consumer must stay apart (ADR-0004). The structure registry is the
channel for facts needing that late binding — a layer asks for a name and never
meets the layer that wrote it. The engine's carried fields — `constraints`, and
the `board` shape it reads size and digit values from — carry the setter's
input, fixed before any layer runs and wanted typed by every reader. The engine
knows those only through read-only protocol views, never the concrete `Puzzle`
types behind them (decision 31).

Who produced the fact used to be the test (ADR-0003); it is now only the
explanation for why the two usually coincide. Read the registry's current
contents against that rule rather than from it: the sole entry is the `"grid"`
of addresses `board` registers, which it builds from `board.size` alone and
which both readers cast. ADR-0004 decisions 2 and 4 move it to a `CellGeometry`
descriptor. Until that lands, the one fact in the registry is one the binding
test would not have put there.
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
    "MalformedPuzzleError",
    "MissingDependencyError",
    "build_engine",
]


class GridfindError(Exception):
    """Base for engine-refusal errors."""


class MalformedPuzzleError(GridfindError):
    """The setter's input is not a well-formed puzzle, so no answer is owed.

    Covers input that contradicts itself (an alias fixing a parameter it also
    states) and input that names what the board never offered (a digit outside
    the board's values).

    Raised, never returned. The answer vocabulary stays found / broke /
    unknown — a malformed puzzle simply never reaches an answer, because
    **broke** is a consistency claim and malformed input has not earned it
    (issue #99, amendments).
    """


class MissingDependencyError(GridfindError):
    """A layer's declared dependency is not present in the stack."""


@dataclass
class Cell:
    """The atom. `content` is its ordered sequence of integer variables."""

    address: str
    content: list[cp_model.IntVar]


class Constraint(Protocol):
    """One constraint's data, riding on the engine for a layer to turn into
    rules.

    A constraint pairs a `type` — the layer that handles it — with `params`,
    that constraint's own settings: a killer cage's cells and target sum, a
    thermo's path. A layer pulls every constraint of its type with
    `constraints_of` and loops them, so one stateless layer serves a puzzle's
    many cages (issue #65).

    `params` is the open JSON boundary (spec #45), so its values are `object` —
    a layer narrows each to the shape it expects.

    The engine stays puzzle-agnostic (spec #4, decision 31): it knows this
    read-only view — `type` and `params` — never the `Constraint` dataclass
    behind it. A layer reads a constraint; it never writes one back.
    """

    @property
    def type(self) -> str: ...

    @property
    def params(self) -> dict[str, object]: ...


class BoardShape(Protocol):
    """A puzzle's board shape facts, riding on the engine opaquely beside
    `constraints` (issue #77) — size and digit values. The same read-only
    decoupling this module's `Constraint` protocol gives `puzzle.Constraint`:
    the engine knows this view, never the concrete `Board` it is."""

    @property
    def size(self) -> int: ...

    @property
    def values(self) -> range: ...


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
    constraints: tuple[Constraint, ...] = ()
    board: BoardShape | None = None

    def constraints_of(self, kind: str) -> list[Constraint]:
        """A data-bearing layer pulls its own constraints by type — the
        accessor beside the `cells` and `structures` a layer already reaches
        into."""
        return [c for c in self.constraints if c.type == kind]

    def add_cell(self, address: str, *, low: int, high: int, width: int = 1) -> Cell:
        content = [
            self.model.new_int_var(low, high, f"{address}.{i}") for i in range(width)
        ]
        cell = Cell(address=address, content=content)
        self.cells[address] = cell
        return cell

    def register_structure(self, name: str, value: object) -> None:
        self.structures[name] = value

    def value(self, solver: cp_model.CpSolver, address: str) -> int:
        """A cell's placed value after a solve — the one home for reading
        cell-content width (issue #72). Relocates today's width-1 behaviour
        unchanged; a width-2 (S-cell) read is `schrodinger`'s to design."""
        return solver.value(self._cell(address).content[0])

    def restrict(self, address: str, digits: Iterable[int]) -> None:
        """Fix a cell to a set of digits — a given or placement is a
        singleton set, a candidate a subset, both one operation (issue #72).
        Each digit is
        checked against the cell's own declared domain, not a borrowed
        global constant, and an unknown address raises."""
        var = self._cell(address).content[0]
        domain = list(var.proto.domain)
        low, high = domain[0], domain[-1]
        allowed = sorted(set(digits))
        for digit in allowed:
            if not low <= digit <= high:
                msg = f"digit {digit} out of range [{low}, {high}] for cell {address!r}"
                raise ValueError(msg)
        self.model.add_allowed_assignments([var], [(digit,) for digit in allowed])

    def _cell(self, address: str) -> Cell:
        cell = self.cells.get(address)
        if cell is None:
            msg = f"address {address!r} is off the board"
            raise ValueError(msg)
        return cell


def build_engine(
    layers: list[Layer],
    constraints: tuple[Constraint, ...] = (),
    board: BoardShape | None = None,
) -> Engine:
    """The two-phase build (spec #4, decision 10): order-insensitive.

    Phase 1 — every layer registers its cells and structures.
    Phase 2 — every layer emits its rules against the now-final structures.

    The puzzle's `constraints` ride on the engine so both phases can query
    them by type (issue #65) — available before phase 1, which is what lets a
    future Schrödinger-style layer widen named cells at register time. `board`
    rides beside them (issue #77): the `board` layer reads its size and values
    to size the grid and bound cells, rather than a fixed constant.

    A layer's declared dependency is a validity check, not a build-order
    crutch: missing dependency refuses the build before either phase runs.
    """
    present = {layer.name for layer in layers}
    for layer in layers:
        for dep in layer.depends_on:
            if dep not in present:
                msg = f"layer {layer.name!r} requires {dep!r}, not in stack"
                raise MissingDependencyError(msg)

    engine = Engine(constraints=constraints, board=board)
    for layer in layers:
        layer.register(engine)
    for layer in layers:
        layer.emit(engine)
    return engine
