from collections.abc import Callable

import pytest

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers import resolve
from gridfind.layers.board import BOARD_SIZE
from gridfind.layers.regions import RegionsDistinct, classic_region_map


def test_regions_distinct_requires_board() -> None:
    (regions_distinct,) = resolve(["regions-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([regions_distinct])


def test_regions_distinct_emits_one_all_different_rule_per_region(
    assert_one_all_different_rule_per_line: Callable[[Engine], None],
) -> None:
    engine = build_engine(resolve(["board", "regions-distinct"]))

    assert_one_all_different_rule_per_line(engine)


def test_regions_distinct_defaults_to_the_classic_3x3_box_map() -> None:
    layer = RegionsDistinct()

    assert layer.region_map == classic_region_map()
    assert len(layer.region_map) == BOARD_SIZE
    for region in layer.region_map:
        assert len(region) == BOARD_SIZE
