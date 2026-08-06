from collections.abc import Callable

import pytest

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers import LAYER_REGISTRY


def test_rows_distinct_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([LAYER_REGISTRY["rows-distinct"]])


def test_rows_distinct_emits_one_all_different_rule_per_row(
    assert_one_all_different_rule_per_line: Callable[[Engine], None],
) -> None:
    engine = build_engine([LAYER_REGISTRY["board"], LAYER_REGISTRY["rows-distinct"]])

    assert_one_all_different_rule_per_line(engine)
