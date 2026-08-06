from collections.abc import Callable

import pytest

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers import resolve


def test_rows_distinct_requires_board() -> None:
    (rows_distinct,) = resolve(["rows-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([rows_distinct])


def test_rows_distinct_emits_one_all_different_rule_per_row(
    assert_one_all_different_rule_per_line: Callable[[Engine], None],
) -> None:
    engine = build_engine(resolve(["board", "rows-distinct"]))

    assert_one_all_different_rule_per_line(engine)
