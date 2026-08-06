import pytest

from gridfind.engine import MissingDependencyError, build_engine
from gridfind.layers import resolve


def test_line_count_distinct_requires_board() -> None:
    (line_count_distinct,) = resolve(["line-count-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([line_count_distinct])


def test_line_count_distinct_emits_counting_rules_not_all_different() -> None:
    engine = build_engine(resolve(["board", "line-count-distinct"]))

    assert len(engine.model.proto.constraints) > 0
    assert not any(c.has_all_diff() for c in engine.model.proto.constraints)
    assert any(c.has_lin_max() for c in engine.model.proto.constraints)
