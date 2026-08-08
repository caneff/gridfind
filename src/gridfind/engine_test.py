from dataclasses import dataclass, field
from typing import cast

import pytest
from ortools.sat.python import cp_model

import gridfind.engine
from gridfind.engine import Engine, MissingDependencyError, build_engine


def test_public_api_surface_is_exactly_the_committed_names() -> None:
    # Issue #28 / ADR-0001: the engine->layer contract's named vocabulary.
    assert gridfind.engine.__all__ == [
        "Cell",
        "Engine",
        "GridfindError",
        "Layer",
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
        build_engine([needs_board])


def test_build_accepts_a_stack_whose_dependency_is_present() -> None:
    board = _FakeLayer(name="board")
    needs_board = _FakeLayer(name="needs-board", depends_on=("board",))

    build_engine([board, needs_board])

    assert needs_board.registered
    assert needs_board.emitted


def test_build_is_order_insensitive() -> None:
    board = _FakeLayer(name="board")
    needs_board = _FakeLayer(name="needs-board", depends_on=("board",))

    build_engine([needs_board, board])

    assert needs_board.registered
    assert needs_board.emitted


@dataclass
class _Record:
    """A test-only puzzle record: the open `Variant` shape without the coupling
    (the engine knows no puzzle concepts, spec #4 decision 31)."""

    type: str
    params: dict[str, object] = field(default_factory=dict)


@dataclass
class _CageLayer:
    """A test-only data-bearing layer (issue #65): one stateless instance pulls
    every record of its type and emits a sum-rule per record, proving a layer's
    `params` reach the code that turns them into rules.

    Scaffolding — delete it (and `_Record` above) once a production data-bearing
    layer (a killer or thermo) lands. Its own test then exercises this mechanism
    against a real constraint, and this stand-in has nothing left to prove.
    """

    name: str = "cage"
    depends_on: tuple[str, ...] = ()

    def register(self, engine: Engine) -> None:
        for name in ("a", "b"):
            engine.add_cell(name, low=1, high=9)

    def emit(self, engine: Engine) -> None:
        for cage in engine.records_of(self.name):
            # params is the open JSON boundary (object) — a layer narrows it.
            names = cast("list[str]", cage.params["cells"])
            total = cast("int", cage.params["sum"])
            cells = [engine.cells[n].content[0] for n in names]
            engine.model.add(sum(cells) == total)


def _solves(engine: Engine) -> bool:
    status = cp_model.CpSolver().solve(engine.model)
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_records_of_returns_only_the_matching_type() -> None:
    engine = build_engine([], (_Record("cage"), _Record("other")))

    assert engine.records_of("cage") == [_Record("cage")]


def test_a_layer_binds_from_its_records_and_a_satisfiable_cage_solves() -> None:
    records = (_Record("cage", {"cells": ["a", "b"], "sum": 5}),)

    engine = build_engine([_CageLayer()], records)

    assert _solves(engine)


def test_a_layer_binds_from_its_records_and_an_impossible_cage_is_infeasible() -> None:
    # Two cells over a 1-9 domain can't sum to 1 — the params reach the rule.
    records = (_Record("cage", {"cells": ["a", "b"], "sum": 1}),)

    engine = build_engine([_CageLayer()], records)

    assert not _solves(engine)
