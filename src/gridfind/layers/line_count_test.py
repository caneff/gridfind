import pytest

from gridfind.engine import MissingDependencyError, build_engine
from gridfind.layers import LAYER_REGISTRY


def test_line_count_distinct_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([LAYER_REGISTRY["line-count-distinct"]])


def test_line_count_distinct_emits_counting_rules_not_all_different() -> None:
    engine = build_engine(
        [LAYER_REGISTRY["board"], LAYER_REGISTRY["line-count-distinct"]]
    )

    assert len(engine.model.proto.constraints) > 0
    assert not any(c.has_all_diff() for c in engine.model.proto.constraints)
    assert any(c.has_lin_max() for c in engine.model.proto.constraints)
