from dataclasses import dataclass

import pytest

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
    """A minimal stand-in for a `Variant` record, used only to exercise
    `Engine.records_of`'s type filter (issue #64)."""

    type: str
    params: dict[str, object]


def test_records_of_returns_only_the_matching_type() -> None:
    # A puzzle carries records of more than one type; records_of must not
    # hand a layer another type's records — a filter that ignores `kind`
    # entirely would still build, so this asserts the filtering itself.
    cage = _Record(type="cage", params={"id": 1})
    thermo = _Record(type="thermo", params={"id": 2})

    engine = build_engine([], records=(cage, thermo))

    assert engine.records_of("cage") == [cage]
    assert engine.records_of("thermo") == [thermo]
    assert engine.records_of("unused") == []
