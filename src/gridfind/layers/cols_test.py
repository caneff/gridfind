from collections.abc import Callable

import pytest

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers import resolve


def test_cols_distinct_requires_board() -> None:
    (cols_distinct,) = resolve(["cols-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([cols_distinct])


def test_cols_distinct_emits_one_all_different_rule_per_col(
    assert_one_all_different_rule_per_line: Callable[[Engine], None],
) -> None:
    engine = build_engine(resolve(["board", "cols-distinct"]))

    assert_one_all_different_rule_per_line(engine)
