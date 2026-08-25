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
absence — so neither hard-depends on schrödinger being present. `cell_geometry`
is a third kind of fact: built from `board.size` alone, no layer's work informs
it, so `build_engine` attaches it directly rather than routing it through the
structure registry's late binding (ADR-0004 decisions 2-4).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol, cast

from ortools.sat.python import cp_model

from gridfind.cell_geometry import BoardShape, CellGeometry, cell_geometry

# The engine->layer contract's named surface (ADR-0001). Layers code
# against these; everything else in the module is implementation detail.
__all__ = [
    "Cell",
    "Engine",
    "GridfindError",
    "Layer",
    "MalformedPuzzleError",
    "MissingDependencyError",
    "build_engine",
    "sole",
]


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
    cell_geometry: CellGeometry
    model: cp_model.CpModel = field(default_factory=cp_model.CpModel)
    cells: dict[str, Cell] = field(default_factory=dict)
    structures: dict[str, object] = field(default_factory=dict)
    constraints: tuple[Constraint, ...] = ()

    def constraints_of(self, kind: str) -> list[Constraint]:
        """A data-bearing layer pulls its own constraints by type — the
        accessor beside the `cells` and `structures` a layer already reaches
        into."""
        return [c for c in self.constraints if c.type == kind]

    def cell_addresses(self, clue: Constraint) -> list[str]:
        """A clue's cell-address list — `params["cells"]`, the open JSON
        boundary narrowed by cast. The one typed home for the cast every
        cage, group-sum, and pair-relation layer would otherwise repeat."""
        return cast("list[str]", clue.params["cells"])

    def add_cell(self, address: str, *, low: int, high: int, width: int = 1) -> Cell:
        """Register a new cell at `address` with `width` int variables, each
        ranging `low` to `high` inclusive. `width` is 1 for an ordinary cell;
        the schrödinger layer passes 2 to widen an S-cell to its pair of
        slots."""
        content = [
            self.model.new_int_var(low, high, f"{address}.{i}") for i in range(width)
        ]
        cell = Cell(address=address, content=content)
        self.cells[address] = cell
        return cell

    def add_board_domain_cell(self, address: str) -> Cell:
        """Register a new cell at `address` carrying the board's own value
        set — the one seam `board` and `outside-cells` both call, so a grid
        cell and a border cell can never disagree on which digits they admit.
        Bounds the variable to the domain's two ends and then restricts it to
        the exact declared set, so a stepped domain (e.g. 2, 4, 6, 8) excludes
        the gaps between them, not just anything between the low and high
        ends."""
        cell = self.add_cell(
            address, low=self.board.values.start, high=self.board.values[-1]
        )
        self.restrict(address, self.board.values)
        return cell

    def register_structure(self, name: str, value: object) -> None:
        """Publish `value` under `name` in the structure registry — the
        late-binding channel (ADR-0004) a producing layer writes to and a
        consuming layer later reads back through its own typed accessor
        (`is_s`, `is_modifier`, `modifier_types`), without the two meeting."""
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

    def modifier_types(self) -> dict[str, str] | None:
        """Per-cell declared modifier type names (address → e.g. `\"doubler\"`),
        or None when the stack has no modifier layer. Registered by the
        concrete modifier layers themselves (`doubler` and any future sibling) —
        `modifier-placement` stays type-blind, so these names come from nowhere
        else. The map is keyed per cell, so the witness names each discovered
        cell from its own entry."""
        return cast("dict[str, str] | None", self.structures.get("modifier_type"))

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

    def assignment(self, solver: cp_model.CpSolver) -> dict[str, tuple[int, ...]]:
        """Every cell's displayed digits after a solve, address → digit
        sequence. A widened S-cell shows both digits; every other cell shows
        its lone d0 — the `is_s ⟺ d1-real` slice the schrödinger layer owns."""
        is_s = self.is_s()
        result: dict[str, tuple[int, ...]] = {}
        for address in self.cells:
            content = self.values(solver, address)
            widened = is_s is not None and bool(solver.value(is_s[address]))
            result[address] = content if widened else content[:1]
        return result

    def discovered_modifiers(self, solver: cp_model.CpSolver) -> dict[str, str]:
        """Every cell the solve placed a modifier on, address → its declared
        type name (e.g. `\"doubler\"`). Empty when the stack has no modifier
        layer. Folds the `is_modifier` indicators against the `modifier_type`
        names both structures own."""
        is_modifier = self.is_modifier()
        modifier_types = self.modifier_types()
        if is_modifier is None or modifier_types is None:
            return {}
        return {
            address: modifier_types[address]
            for address in self.cells
            if bool(solver.value(is_modifier[address]))
        }

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

    def value_expr(self, address: str) -> cp_model.IntVar:
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

    def real_digit_slots(
        self, address: str
    ) -> list[tuple[cp_model.IntVar, cp_model.IntVar | None]]:
        """A cell's real digit(s), each paired with its guard: `d0` is always
        real (guard `None`); `d1`, when present, is real only when `is_s`
        holds. This is digit mode's gated read (ADR-0019 decision 6) — the
        engine's one contribution to a digit-set clue (clone, and any future
        sibling), which supplies only its predicate and adds
        `.only_enforce_if(guard)` on the gated term, never seeing the
        sentinel that fills a singleton's second slot. A width-1 cell (no
        schrödinger layer in the stack) degrades to the single `d0` slot."""
        content = self.contents(address)
        if len(content) == 1:
            return [(content[0], None)]
        is_s = self.is_s()
        if is_s is None:
            raise GridfindError("width-2 cell without an is_s structure")
        return [(content[0], None), (content[1], is_s[address])]

    def domain(self, address: str) -> list[int]:
        """The digit values a cell may hold, ascending.

        A solver variable states its domain as one closed interval: a low
        bound and a high bound. This reads those two bounds and expands them
        into the full ascending list.
        """
        domain = list(self.d0(address).proto.domain)
        low, high = domain[0], domain[-1]
        return list(range(low, high + 1))

    def require_in_domain(self, address: str, digits: Iterable[int]) -> None:
        """Refuse a digit the board never offered — the one home for the
        malformed-digit guard, checked against the board's own declared
        values, not a domain re-derived from the solver variable. Shared by
        `restrict` (d0 only) and the applier's directive checks, which reach
        both pair slots of a Schrödinger cell."""
        for digit in digits:
            if digit not in self.board.values:
                values = list(self.board.values)
                msg = f"digit {digit} is not among {values} for cell {address!r}"
                raise MalformedPuzzleError(msg)

    def restrict(self, address: str, digits: Iterable[int]) -> None:
        """Fix a cell to a set of digits — a given or placement is a
        singleton set, a candidate a subset, both one operation. An
        unknown address raises separately."""
        var = self.d0(address)
        allowed = sorted(set(digits))
        self.require_in_domain(address, allowed)
        self.model.add_allowed_assignments([var], [(digit,) for digit in allowed])

    def reify_holds(
        self, slots: Sequence[cp_model.LinearExprT], digit: int, label: str
    ) -> list[cp_model.IntVar]:
        """For each slot, a reified bool tracking whether it holds `digit` — the
        "does this slot hold this digit" idiom. It lives on the engine, the spine
        both the layers package and `verdict` legitimately depend on, because
        both need it: the layer emit-helpers (`emit_distinct_count`,
        `emit_house`) fold it into house rules, and `verdict` ORs it across a
        cell's slots for a half-S-cell's "digit appears among the two slots"
        membership. `layers._base` is layers-internal, so a shared
        helper cannot live there. `slots` takes a general linear expression,
        not just a raw content var, so `quadruple` can reify presence over
        `value_expr` (ADR-0009's doubler/S-cell-aware value) the same way."""
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
    to bound cells, rather than a fixed constant. `cell_geometry` is built from
    `board` once, here, before either phase runs, so every layer's `RxCy`
    address grid is the same object (ADR-0004).

    A layer's declared dependency is a validity check, not a build-order
    crutch: missing dependency refuses the build before either phase runs.
    """
    present = {layer.name for layer in layers}
    for layer in layers:
        for dep in layer.depends_on:
            if dep not in present:
                msg = f"layer {layer.name!r} requires {dep!r}, not in stack"
                raise MissingDependencyError(msg)

    engine = Engine(
        constraints=constraints, board=board, cell_geometry=cell_geometry(board)
    )
    for layer in layers:
        layer.register(engine)
    for layer in layers:
        layer.emit(engine)
    return engine
