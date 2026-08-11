"""The engine spine: cells, the structure registry, and the two-phase build.

Two channels reach a layer, and the line between them is whether the producer
and the consumer must stay apart (ADR-0004). The structure registry is the
channel for facts needing that late binding — a layer asks for a name and never
meets the layer that wrote it. The engine's carried fields — `constraints`, and
the `board` shape it reads size and digit values from — carry the setter's
input, fixed before any layer runs and wanted typed by every reader. The engine
knows those only through read-only protocol views, never the concrete `Puzzle`
types behind them (decision 31).

`is_s`, registered by the schrödinger layer, is read back by `distinct` and
`verdict` through the `engine.is_s()` accessor's `.get`, which tolerates its
absence — so neither hard-depends on schrödinger being present. `grid`, the
addresses `board` registers, is the anomaly: built from `board.size` alone, a
fact no layer's work informs, so it belongs on the board, not in the late-
binding registry. ADR-0004 decisions 2 and 4 move it to a `CellGeometry`
descriptor.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

from ortools.sat.python import cp_model

# The engine->layer contract's named surface (ADR-0001). Layers code
# against these; everything else in the module is implementation detail.
__all__ = [
    "Cell",
    "Combine",
    "Engine",
    "GridfindError",
    "Layer",
    "MalformedPuzzleError",
    "MissingDependencyError",
    "build_engine",
    "sole",
]

Combine = Literal["sum", "concat"]
"""How a two-digit S-cell's digits combine into one value: `sum` adds them
(2 + 3 = 5); `concat` reads them base-10 with the first digit (`d0`)
most-significant (2, 3 → 23). One choice per puzzle, owned by the schrödinger
layer, which uses it to build each S-cell's value channel (ADR-0009). A
single digit has nothing to combine."""


class GridfindError(Exception):
    """Base for engine-refusal errors."""


class MalformedPuzzleError(GridfindError):
    """The setter's input is not a well-formed puzzle, so no answer is owed.

    Covers input that contradicts itself (an alias fixing a parameter it also
    states) and input that names what the board never offered — a digit
    outside the board's values, or an address the board doesn't have (a given,
    placement, or candidate naming a cell that isn't on the grid).

    Raised, never returned. The answer vocabulary stays found / broke /
    unknown — a malformed puzzle simply never reaches an answer, because
    **broke** is a consistency claim and malformed input has not earned it.
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
    many cages.

    `params` is the open JSON boundary, so its values are `object` —
    a layer narrows each to the shape it expects.

    The engine stays puzzle-agnostic (decision 31): it knows this
    read-only view — `type` and `params` — never the `Constraint` dataclass
    behind it. A layer reads a constraint; it never writes one back.
    """

    @property
    def type(self) -> str: ...

    @property
    def params(self) -> dict[str, object]: ...


class BoardShape(Protocol):
    """A puzzle's board shape facts, riding on the engine opaquely beside
    `constraints` — size and digit values. The same read-only
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

    board: BoardShape
    model: cp_model.CpModel = field(default_factory=cp_model.CpModel)
    cells: dict[str, Cell] = field(default_factory=dict)
    structures: dict[str, object] = field(default_factory=dict)
    constraints: tuple[Constraint, ...] = ()

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

    def is_s(self) -> dict[str, cp_model.IntVar] | None:
        """The schrödinger layer's per-cell S-cell indicators, or None when the
        stack has no schrödinger layer — read through `.get`, so a reader
        tolerates its absence (ADR-0004). The one typed home for the cast every
        S-aware reader would otherwise repeat."""
        return cast("dict[str, cp_model.IntVar] | None", self.structures.get("is_s"))

    def is_modifier(self) -> dict[str, cp_model.IntVar] | None:
        """`modifier-placement`'s per-cell discovered-modifier indicators, or
        None when the stack has no modifier layer — read through `.get`, the
        same absence-tolerant idiom as `is_s` (ADR-0004)."""
        return cast(
            "dict[str, cp_model.IntVar] | None", self.structures.get("is_modifier")
        )

    def modifier_type(self) -> str | None:
        """The puzzle's one declared modifier type name (e.g. `\"doubler\"`),
        or None when the stack has no modifier layer. Registered by the
        concrete modifier layer itself (`doubler` and any future sibling) —
        `modifier-placement` stays type-blind, so this name comes from
        nowhere else."""
        return cast("str | None", self.structures.get("modifier_type"))

    def grid(self) -> list[list[str]]:
        """The board's addresses laid out row-major, registered by `board`."""
        return cast("list[list[str]]", self.structures["grid"])

    def values(self, solver: cp_model.CpSolver, address: str) -> tuple[int, ...]:
        """A cell's placed content sequence after a solve. A
        width-1 cell hands back a length-1 sequence, so a caller that wants a
        single digit reads it itself; a width-2 (S-cell) read is
        `schrodinger`'s to combine."""
        return tuple(solver.value(v) for v in self._cell(address).content)

    def contents(self, address: str) -> list[cp_model.IntVar]:
        """A cell's raw content sequence, for a layer building an expression
        over it. A width-1 cell hands back a length-1 sequence."""
        return self._cell(address).content

    def value(self, solver: cp_model.CpSolver, address: str) -> int:
        """A not-yet-widened cell's one placed digit after a solve — the
        singular read for a rule that doesn't handle Schrödinger cells.
        Raises on a widened S-cell; an S-aware reader takes the
        whole sequence through `values`."""
        return sole(self.values(solver, address))

    def content(self, address: str) -> cp_model.IntVar:
        """A not-yet-widened cell's one content variable, for a rule building
        an expression over a single digit. Raises on a widened S-cell like
        `value` does; an S-aware reader takes the whole sequence through
        `contents`."""
        return sole(self.contents(address))

    def d0(self, address: str) -> cp_model.IntVar:
        """A cell's first content variable — d0, which `schrodinger` keeps
        always a real digit. Unlike `content` it never raises on
        a widened S-cell: d0 is well-defined for both, so a read that wants
        the cell's real digit and nothing about its S-cell axis takes d0
        whatever the width. A width-1 cell's d0 is its only slot."""
        return self._cell(address).content[0]

    def base_value(self, address: str) -> cp_model.IntVar:
        """A cell's value beneath any modifier — its `s_value` when the
        schrödinger layer reified one (its two digits combined under the
        puzzle's `combine` rule), else its digit. This is the value a modifier
        layer maps: the doubler reads it and reifies twice it (ADR-0010), so
        the `2·` never has to name the schrödinger channel. `value_expr` layers
        the modifier's mapped value on top of it."""
        s_value = cast("dict[str, cp_model.IntVar]", self.structures.get("s_value", {}))
        if address in s_value:
            return s_value[address]
        return self.content(address)

    def value_expr(self, address: str) -> cp_model.LinearExprT:
        """A cell's value as a model-build-time expression, for a constraint
        that must put a cell's *value* (not its raw digit) into a CP rule, such
        as a values-distinct cage (ADR-0009). A modifier maps the value beneath
        it, so the value is the `modifier_value` a modifier reified for the cell
        — a doubler's `2·d0`, or `2·s_value` for a doubled S-cell (ADR-0010) —
        else the unmodified `base_value`. Each reader stays blind to which
        layer built the value it gets."""
        modifier_value = cast(
            "dict[str, cp_model.IntVar]", self.structures.get("modifier_value", {})
        )
        if address in modifier_value:
            return modifier_value[address]
        return self.base_value(address)

    def domain(self, address: str) -> list[int]:
        """The digit values a cell may hold, ascending, decoded from its
        solver domain rather than from the two ends of it.

        A solver variable states its domain as flat pairs of closed
        intervals. Every board gridfind builds today gives a cell one
        unbroken interval, so the multi-interval path is decoded but not yet
        exercised; a constraint that holds a cell to a stepped digit set is
        what will exercise it.
        """
        domain = list(self.d0(address).proto.domain)
        return [
            digit
            for low, high in zip(domain[::2], domain[1::2], strict=True)
            for digit in range(low, high + 1)
        ]

    def restrict(self, address: str, digits: Iterable[int]) -> None:
        """Fix a cell to a set of digits — a given or placement is a
        singleton set, a candidate a subset, both one operation.
        Each digit is checked against the board's own declared values, the
        one authority on what a cell may hold, not a domain re-derived from
        the solver variable — an unknown address raises separately."""
        var = self.d0(address)
        allowed = sorted(set(digits))
        for digit in allowed:
            if digit not in self.board.values:
                values = list(self.board.values)
                msg = f"digit {digit} is not among {values} for cell {address!r}"
                raise MalformedPuzzleError(msg)
        self.model.add_allowed_assignments([var], [(digit,) for digit in allowed])

    def reify_holds(
        self, slots: list[cp_model.IntVar], digit: int, label: str
    ) -> list[cp_model.IntVar]:
        """For each slot, a reified bool tracking whether it holds `digit` — the
        "does this slot hold this digit" idiom. It lives on the engine, the spine
        both the layers package and `verdict` legitimately depend on, because
        both need it: the layer emit-helpers (`emit_distinct_count`,
        `emit_house`) fold it into house rules, and `verdict` ORs it across a
        cell's slots for a half-S-cell's "digit appears among the two slots"
        membership. `layers._base` is layers-internal, so a shared
        helper cannot live there."""
        holds_digit = []
        for i, slot in enumerate(slots):
            indicator = self.model.new_bool_var(f"{label}.holds{digit}.{i}")
            self.model.add(slot == digit).only_enforce_if(indicator)
            self.model.add(slot != digit).only_enforce_if(indicator.negated())
            holds_digit.append(indicator)
        return holds_digit

    def _cell(self, address: str) -> Cell:
        cell = self.cells.get(address)
        if cell is None:
            msg = f"address {address!r} is off the board"
            raise MalformedPuzzleError(msg)
        return cell


def sole[Read](reads: Sequence[Read]) -> Read:
    """The one element of a not-yet-widened cell's content or value sequence.
    Raises when the cell was widened to an S-cell: a rule that folds with
    `sole` has not been taught Schrödinger cells yet, and silently taking the
    first slot would drop the second. Where a rule *does* handle S-cells it
    reads the sequence whole, never through `sole`."""
    if len(reads) != 1:
        msg = (
            f"expected a width-1 cell, got a length-{len(reads)} content — "
            "this rule is not Schrödinger-ready yet"
        )
        raise GridfindError(msg)
    return reads[0]


def build_engine(
    layers: list[Layer],
    constraints: tuple[Constraint, ...] = (),
    *,
    board: BoardShape,
) -> Engine:
    """The two-phase build (decision 10): order-insensitive.

    Phase 1 — every layer registers its cells and structures.
    Phase 2 — every layer emits its rules against the now-final structures.

    The puzzle's `constraints` ride on the engine so both phases can query
    them by type — available before phase 1, which is what lets a
    future Schrödinger-style layer widen named cells at register time. `board`
    rides beside them: the `board` layer reads its size and values
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
