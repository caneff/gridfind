from dataclasses import dataclass, field
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from ortools.sat.python import cp_model

import gridfind.engine
from gridfind.engine import (
    Engine,
    Fold,
    GridfindError,
    Layer,
    MalformedPuzzleError,
    MissingDependencyError,
    ValueElement,
    build_engine,
    sole,
)
from gridfind.puzzle import Board

BOARD = Board(size=9)


def test_malformed_puzzle_refusals_answer_to_the_base_refusal_handler() -> None:
    # A tripwire like the one below, not a behavior test: several call sites
    # raise this error, and callers catch the whole family with one
    # `except GridfindError`. Re-parenting it would silently stop those
    # handlers firing, so the parent is pinned here. See the class docstring
    # for why the error exists.
    assert issubclass(MalformedPuzzleError, GridfindError)


def test_public_api_surface_is_exactly_the_committed_names() -> None:
    # A tripwire, not a behavior test: the only thing it enforces is that
    # changing this list is a public API change. Downstream agents type-check
    # against the engine->layer contract via py.typed, so editing `__all__`
    # must be a deliberate act with this expectation updated alongside it.
    # (ADR-0001: the contract's named vocabulary.)
    assert gridfind.engine.__all__ == [
        "Cell",
        "Engine",
        "Fold",
        "GridfindError",
        "Layer",
        "MalformedPuzzleError",
        "MissingDependencyError",
        "ValueElement",
        "build_engine",
        "sole",
    ]


@dataclass
class _FakeLayer:
    """A minimal stand-in layer, used only to exercise the build's generic
    dependency-refusal mechanism (decision 10)."""

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
    the coupling (the engine knows no puzzle concepts, decision 31)."""

    type: str
    params: dict[str, object] = field(default_factory=dict)


@dataclass
class _CageLayer:
    """A test-only data-bearing layer: one stateless instance
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


def test_values_reads_a_cells_placed_content_sequence_after_a_solve() -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("x", low=1, high=9)
    engine.model.add(cell.content[0] == 7)
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    assert engine.values(solver, "x") == (7,)


def test_values_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=BOARD)
    solver = cp_model.CpSolver()

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.values(solver, "nope")


def test_contents_returns_a_cells_raw_content_sequence() -> None:
    engine = build_engine([], board=Board(size=9))
    cell = engine.add_cell("x", low=1, high=9)

    assert engine.contents("x") is cell.content


def test_contents_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=Board(size=9))

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.contents("nope")


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
    assert engine.values(solver, "x") == (7,)


def test_restrict_pins_a_cell_to_a_digit_subset() -> None:
    engine = build_engine([], board=BOARD)
    engine.add_cell("x", low=1, high=9)

    engine.restrict("x", {1, 2})

    solver = cp_model.CpSolver()
    solver.solve(engine.model)
    assert engine.values(solver, "x") in ((1,), (2,))


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


def test_sole_returns_the_one_element_of_a_width_1_read() -> None:
    assert sole(("7",)) == "7"
    assert sole([42]) == 42


def test_sole_raises_on_a_widened_s_cell_read() -> None:
    # A rule that folds with `sole` isn't Schrödinger-ready: handed a
    # width-2 S-cell read it must refuse loudly, not silently keep the first
    # slot and drop the second.
    with pytest.raises(GridfindError, match="not Schrödinger-ready"):
        sole((3, 5))


def test_content_returns_the_one_variable_of_a_width_1_cell() -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("x", low=1, high=9)

    assert engine.content("x") is cell.content[0]


def test_content_raises_on_a_widened_s_cell() -> None:
    engine = build_engine([], board=BOARD)
    engine.add_cell("s", low=1, high=9, width=2)

    with pytest.raises(GridfindError, match="not Schrödinger-ready"):
        engine.content("s")


def test_value_reads_the_one_placed_digit_of_a_width_1_cell() -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("x", low=1, high=9)
    engine.model.add(cell.content[0] == 4)
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    assert engine.value(solver, "x") == 4


def test_value_raises_on_a_widened_s_cell() -> None:
    engine = build_engine([], board=BOARD)
    engine.add_cell("s", low=1, high=9, width=2)
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    with pytest.raises(GridfindError, match="not Schrödinger-ready"):
        engine.value(solver, "s")


def test_d0_returns_the_first_slot_and_never_raises_on_a_widened_cell() -> None:
    # d0 is the always-real first slot: defined for a plain cell and an S-cell
    # alike, so unlike `content` it must not refuse a width-2 read.
    engine = build_engine([], board=BOARD)
    plain = engine.add_cell("x", low=1, high=9)
    s_cell = engine.add_cell("s", low=1, high=9, width=2)

    assert engine.d0("x") is plain.content[0]
    assert engine.d0("s") is s_cell.content[0]


@given(a=st.integers(-5, 5), b=st.integers(-5, 5), digit=st.integers(1, 9))
def test_value_element_apply_is_the_affine_read(a: int, b: int, digit: int) -> None:
    assert ValueElement(a=a, b=b).apply(digit) == a * digit + b


def test_value_element_default_is_the_identity() -> None:
    assert ValueElement().apply(7) == 7


def test_elements_default_is_one_identity_element_per_content_slot() -> None:
    engine = build_engine([], board=BOARD)
    engine.add_cell("x", low=1, high=9)
    engine.add_cell("s", low=1, high=9, width=2)

    assert engine.elements("x") == [ValueElement()]
    assert engine.elements("s") == [ValueElement(), ValueElement()]


def test_elements_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=BOARD)

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.elements("nope")


def test_elements_reads_a_registered_override_over_the_default() -> None:
    engine = build_engine([], board=BOARD)
    engine.add_cell("x", low=1, high=9)
    doubled = [ValueElement(a=2)]
    engine.register_structure("value_elements", {"x": doubled})

    assert engine.elements("x") == doubled


@given(digit=st.integers(1, 9), fold=st.sampled_from(["sum", "positional"]))
def test_folded_value_of_a_singleton_is_byte_identical_to_value(
    digit: int, fold: Fold
) -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("x", low=1, high=9)
    engine.model.add(cell.content[0] == digit)
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    folded = engine.folded_value(solver, "x", fold)

    assert folded == engine.value(solver, "x") == digit


@pytest.mark.parametrize(
    ("fold", "expected"),
    [
        pytest.param("sum", 8, id="sum-adds-the-terms"),
        pytest.param("positional", 35, id="positional-reads-10-times-d0-plus-d1"),
    ],
)
def test_fold_reads_a_two_element_value(fold: Fold, expected: int) -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("s", low=1, high=9, width=2)
    engine.model.add(cell.content[0] == 3)
    engine.model.add(cell.content[1] == 5)
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    assert engine.folded_value(solver, "s", fold) == expected


@given(a=st.integers(-5, 5), b=st.integers(-5, 5), digit=st.integers(1, 9))
def test_folded_value_folds_a_registered_affine_element(
    a: int, b: int, digit: int
) -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("x", low=1, high=9)
    engine.model.add(cell.content[0] == digit)
    engine.register_structure("value_elements", {"x": [ValueElement(a=a, b=b)]})
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    assert engine.folded_value(solver, "x", "sum") == a * digit + b


def test_folded_value_on_an_off_board_address_raises() -> None:
    engine = build_engine([], board=BOARD)
    solver = cp_model.CpSolver()

    with pytest.raises(MalformedPuzzleError, match="off the board"):
        engine.folded_value(solver, "nope", "sum")


def test_folded_value_raises_on_an_unknown_fold_name() -> None:
    engine = build_engine([], board=BOARD)
    cell = engine.add_cell("x", low=1, high=9)
    engine.model.add(cell.content[0] == 4)
    solver = cp_model.CpSolver()
    solver.solve(engine.model)

    with pytest.raises(GridfindError, match="unknown fold"):
        engine.folded_value(solver, "x", cast("Fold", "product"))
