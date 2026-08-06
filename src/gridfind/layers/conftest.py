"""Shared test fixtures for the layers package.

`assert_one_all_different_rule_per_line` is the common shape of the
rows/cols/regions-distinct emit tests. It lives here as a fixture so the three
per-layer test files stay independent without copying the assertion body
(issue #20's dedup, preserved across issue #17's per-layer split).
"""

from collections.abc import Callable

import pytest

from gridfind.engine import Engine
from gridfind.layers.board import BOARD_SIZE


@pytest.fixture
def assert_one_all_different_rule_per_line() -> Callable[[Engine], None]:
    def _assert(engine: Engine) -> None:
        assert len(engine.model.proto.constraints) == BOARD_SIZE
        for constraint in engine.model.proto.constraints:
            assert constraint.has_all_diff()
            assert len(constraint.all_diff.exprs) == BOARD_SIZE

    return _assert
