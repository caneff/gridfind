from dataclasses import dataclass, field
from typing import cast

import pytest
from ortools.sat.python import cp_model

import gridfind.engine
from gridfind.engine import (
    Engine,
    GridfindError,
    Layer,
    MalformedPuzzleError,
    MissingDependencyError,
    build_engine,
)
from gridfind.puzzle import Board

BOARD = Board(size=9)


def test_malformed_puzzle_refusals_answer_to_the_base_refusal_handler() -> None:
    # A tripwire like the one below, not a behavior test: #101, #102 and #107
    # all raise this error, and callers catch the whole family with one
    # `except GridfindError`. Re-parenting it would silently stop those
    # handlers firing, so the parent is pinned here. See the class docstring
    # for why the error exists.
    assert issubclass(MalformedPuzzleError, GridfindError)


def test_public_api_surface_is_exactly_the_committed_names() -> None:
    # A tripwire, not a behavior test: the only thing it enforces is that
    # changing this list is a public API change. Downstream agents type-check
    # against the engine->layer contract via py.typed, so editing `__all__`
    # must be a deliberate act with this expectation updated alongside it.
    # (Issue #28 / ADR-0001: the contract's named vocabulary.)
    assert gridfind.engine.__all__ == [
        "Cell",
        "Engine",
        "GridfindError",
        "Layer",
        "MalformedPuzzleError",
        "MissingDependencyError",
        "build_engine",
    ]


@dataclass
class _FakeLayer:
    """A minimal stand-in layer, used only to exercise the build's generic
    dependency-refusal mechanism (spec #4, decision 10)."""

    name: str
    depends_on: tuple[str, ...] = ()
    registered: bool = False
    emitted: bool = False

    def register(self, engine: Engine) -> None:
        self.registered = True

    def emit(self, engine: Engine) -> None:
        self.emitted = True


def test_build_refuses_a_stack_with_an_unmet_dependency() -> None:
    needs_board = _FakeLayer(name="needs-board", depends_on=("board",))

    with pytest.raises(MissingDependencyError):
        build_engine([needs_board], board=BOARD)


@pytest.mark.parametrize(
    "dependent_first",
    [False, True],
    ids=["dependency-first", "dependent-first"],
)
def test_build_satisfies_a_dependency_regardless_of_stack_order(
    dependent_first: bool,
) -> None:
    board = _FakeLayer(name="board")
    needs_board = _FakeLayer(name="needs-board", depends_on=("board",))
    stack: list[Layer] = [board, needs_board]
    if dependent_first:
        stack.reverse()

    build_engine(stack, board=BOARD)

    assert needs_board.registered
    assert needs_board.emitted


@dataclass
class _Constraint:
    """A test-only puzzle constraint: the open `Constraint` shape without
    the coupling (the engine knows no puzzle concepts, spec #4 decision 31)."""

    type: str
    params: dict[str, object] = field(default_factory=dict)


@dataclass
class _CageLayer:
    """A test-only data-bearing layer (issue #65): one stateless instance
    pulls every constraint of its type and emits a sum-rule per constraint,
    proving a layer's `params` reach the code that turns them into rules.

    Scaffolding — delete it (and `_Constraint` above) once a production
    data-bearing layer (a killer or thermo) lands. Its own test then exercises
    this mechanism against a real constraint, and this stand-in has nothing
    left to prove."""

    name: str = "cage"
    depends_on: tuple[str, ...] = ()

    def register(self, engine: Engine) -> None:
        for name in ("a", "b"):
            engine.add_cell(name, low=1, high=9)

    def emit(self, engine: Engine) -> None:
        for cage in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — a layer narrows it.
            names = cast("list[str]", cage.params["cells"])
            total = cast("int", cage.params["sum"])
            cells = [engine.cells[n].content[0] for n in names]
            engine.model.add(sum(cells) == total)


def _solves(engine: Engine) -> bool:
    status = cp_model.CpSolver().solve(engine.model)
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_constraints_of_returns_only_the_matching_type() -> None:
    engine = build_engine([], (_Constraint("cage"), _Constraint("other")), board=BOARD)

    assert engine.constraints_of("cage") == [_Constraint("cage")]


def test_a_layer_binds_from_its_constraints_and_a_cage_solves() -> None:
    constraints = (_Constraint("cage", {"cells": ["a", "b"], "sum": 5}),)

    engine = build_engine([_CageLayer()], constraints, board=BOARD)

    assert _solves(engine)


def test_a_layer_binds_and_an_impossible_cage_is_infeasible() -> None:
    # Two cells over a 1-9 domain can't sum to 1 — the params reach the rule.
    constraints = (_Constraint("cage", {"cells": ["a", "b"], "sum": 1}),)

    engine = build_engine([_CageLayer()], constraints, board=BOARD)

    assert not _solves(engine)


def test_value_reads_a_cells_placed_value_after_a_solve() -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("x", low=1, high=9)
    engine.model.add(cell.content[0] == 7)
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    assert engine.value(solver, "x") == 7


def test_value_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=BOARD)
    solver = cp_model.CpSolver()

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.value(solver, "nope")


def test_content_returns_a_cells_primary_content_variable() -> None:
    engine = build_engine([], board=Board(size=9))
    cell = engine.add_cell("x", low=1, high=9)

    assert engine.content("x") is cell.content[0]


def test_content_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=Board(size=9))

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.content("nope")


def test_domain_returns_a_cells_declared_digit_values_ascending() -> None:
    engine = build_engine([], board=Board(size=9))
    engine.add_cell("x", low=3, high=7)

    assert engine.domain("x") == [3, 4, 5, 6, 7]


def test_domain_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=Board(size=9))

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.domain("nope")


def test_restrict_pins_a_cell_to_a_singleton_digit() -> None:
    engine = build_engine([], board=BOARD)
    engine.add_cell("x", low=1, high=9)

    engine.restrict("x", {7})

    solver = cp_model.CpSolver()
    solver.solve(engine.model)
    assert engine.value(solver, "x") == 7


def test_restrict_pins_a_cell_to_a_digit_subset() -> None:
    engine = build_engine([], board=BOARD)
    engine.add_cell("x", low=1, high=9)

    engine.restrict("x", {1, 2})

    solver = cp_model.CpSolver()
    solver.solve(engine.model)
    assert engine.value(solver, "x") in (1, 2)


def test_restrict_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=BOARD)

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.restrict("nope", {1})


def test_restrict_checks_a_digit_against_the_boards_declared_values() -> None:
    # The cell's own bounds are wider than the board's values — restrict
    # rejects on the board's declared set, not a domain re-derived from the
    # solver variable's own bounds.
    engine = build_engine([], board=Board(size=5))
    engine.add_cell("x", low=1, high=9)

    with pytest.raises(MalformedPuzzleError, match=r"9.*'x'"):
        engine.restrict("x", {9})
