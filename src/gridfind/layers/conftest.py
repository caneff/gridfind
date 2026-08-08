"""Shared test fixtures for the layers package.

`assert_one_all_different_rule_per_group` is the common shape of the
distinct-layer emit tests: one AllDifferent rule per group, each over a full
line's worth of cells. It lives here as a fixture so `distinct_test` and any
other layer test share the assertion body without copying it (issue #20's
dedup, carried through the issue #37 unification).
"""

from collections.abc import Callable

import pytest

from gridfind.engine import Engine

_BOARD_SIZE = 9  # the board these shared tests build against


@pytest.fixture
def assert_one_all_different_rule_per_group() -> Callable[[Engine], None]:
    def _assert(engine: Engine) -> None:
        assert len(engine.model.proto.constraints) == _BOARD_SIZE
        for constraint in engine.model.proto.constraints:
            assert constraint.has_all_diff()
            assert len(constraint.all_diff.exprs) == _BOARD_SIZE

    return _assert
