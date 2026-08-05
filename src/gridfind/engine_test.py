from dataclasses import dataclass

import pytest

from gridfind.engine import Engine, MissingDependencyError, build_engine


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


def test_build_refuses_a_stack_with_an_unmet_dependency():
    needs_board = _FakeLayer(name="needs-board", depends_on=("board",))

    with pytest.raises(MissingDependencyError):
        build_engine([needs_board])


def test_build_accepts_a_stack_whose_dependency_is_present():
    board = _FakeLayer(name="board")
    needs_board = _FakeLayer(name="needs-board", depends_on=("board",))

    build_engine([board, needs_board])

    assert needs_board.registered
    assert needs_board.emitted


def test_build_is_order_insensitive():
    board = _FakeLayer(name="board")
    needs_board = _FakeLayer(name="needs-board", depends_on=("board",))

    build_engine([needs_board, board])

    assert needs_board.registered
    assert needs_board.emitted
