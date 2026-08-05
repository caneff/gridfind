import pytest

from gridfind.engine import MissingDependencyError, build_engine
from gridfind.layers import (
    BOARD_SIZE,
    LAYER_REGISTRY,
    RegionsDistinct,
    UnknownLayerError,
    classic_region_map,
    resolve,
)


def test_board_registers_every_grid_cell_with_rxcy_addressing():
    (board,) = resolve(["board"])
    engine = build_engine([board])

    assert len(engine.cells) == BOARD_SIZE * BOARD_SIZE
    assert set(engine.cells) == {
        f"R{r}C{c}" for r in range(1, BOARD_SIZE + 1) for c in range(1, BOARD_SIZE + 1)
    }
    for cell in engine.cells.values():
        assert len(cell.content) == 1


def test_board_emits_no_rules():
    (board,) = resolve(["board"])
    engine = build_engine([board])

    assert len(engine.model.proto.constraints) == 0


def test_resolve_rejects_an_unregistered_layer_name():
    with pytest.raises(UnknownLayerError):
        resolve(["not-a-real-layer"])


def test_rows_distinct_requires_board():
    (rows_distinct,) = resolve(["rows-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([rows_distinct])


def test_rows_distinct_emits_one_all_different_rule_per_row():
    engine = build_engine(resolve(["board", "rows-distinct"]))

    assert len(engine.model.proto.constraints) == BOARD_SIZE
    for constraint in engine.model.proto.constraints:
        assert constraint.has_all_diff()
        assert len(constraint.all_diff.exprs) == BOARD_SIZE


def test_line_count_distinct_requires_board():
    (line_count_distinct,) = resolve(["line-count-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([line_count_distinct])


def test_line_count_distinct_emits_counting_rules_not_all_different():
    engine = build_engine(resolve(["board", "line-count-distinct"]))

    assert len(engine.model.proto.constraints) > 0
    assert not any(c.has_all_diff() for c in engine.model.proto.constraints)
    assert any(c.has_lin_max() for c in engine.model.proto.constraints)


def test_cols_distinct_requires_board():
    (cols_distinct,) = resolve(["cols-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([cols_distinct])


def test_cols_distinct_emits_one_all_different_rule_per_col():
    engine = build_engine(resolve(["board", "cols-distinct"]))

    assert len(engine.model.proto.constraints) == BOARD_SIZE
    for constraint in engine.model.proto.constraints:
        assert constraint.has_all_diff()
        assert len(constraint.all_diff.exprs) == BOARD_SIZE


def test_regions_distinct_requires_board():
    (regions_distinct,) = resolve(["regions-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([regions_distinct])


def test_regions_distinct_emits_one_all_different_rule_per_region():
    engine = build_engine(resolve(["board", "regions-distinct"]))

    assert len(engine.model.proto.constraints) == BOARD_SIZE
    for constraint in engine.model.proto.constraints:
        assert constraint.has_all_diff()
        assert len(constraint.all_diff.exprs) == BOARD_SIZE


def test_regions_distinct_defaults_to_the_classic_3x3_box_map():
    layer = RegionsDistinct()

    assert layer.region_map == classic_region_map()
    assert len(layer.region_map) == BOARD_SIZE
    for region in layer.region_map:
        assert len(region) == BOARD_SIZE


def test_regions_distinct_irregular_registry_entry_uses_a_different_map():
    classic = LAYER_REGISTRY["regions-distinct"]
    irregular = LAYER_REGISTRY["regions-distinct-irregular"]

    assert isinstance(classic, RegionsDistinct)
    assert isinstance(irregular, RegionsDistinct)
    assert classic.region_map != irregular.region_map
    assert len(irregular.region_map) == BOARD_SIZE
    for region in irregular.region_map:
        assert len(region) == BOARD_SIZE
