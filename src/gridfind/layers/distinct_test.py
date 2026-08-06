from collections.abc import Callable

import pytest

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers import LAYER_REGISTRY
from gridfind.layers.distinct import boxes, cols, rows


def _grid(size: int) -> list[list[str]]:
    # Each cell a unique label so a partition's groups are identifiable.
    return [[f"r{r}c{c}" for c in range(size)] for r in range(size)]


def test_rows_partition_is_the_grid_rows_unchanged() -> None:
    grid = _grid(4)

    assert list(rows(grid)) == grid


def test_cols_partition_is_the_transpose() -> None:
    grid = _grid(4)

    assert [list(col) for col in cols(grid)] == [
        ["r0c0", "r1c0", "r2c0", "r3c0"],
        ["r0c1", "r1c1", "r2c1", "r3c1"],
        ["r0c2", "r1c2", "r2c2", "r3c2"],
        ["r0c3", "r1c3", "r2c3", "r3c3"],
    ]


def test_boxes_partition_covers_every_cell_exactly_once() -> None:
    # Size-agnostic: 3x3 boxes cut from whatever grid — here a 6x6, four boxes
    # of nine, together the whole grid with no cell repeated.
    grid = _grid(6)
    groups = [list(g) for g in boxes(grid)]

    assert len(groups) == 4
    for group in groups:
        assert len(group) == 9
    flat = [cell for group in groups for cell in group]
    assert sorted(flat) == sorted(cell for row in grid for cell in row)


def test_boxes_first_box_is_the_top_left_3x3_block() -> None:
    grid = _grid(9)

    assert set(next(iter(boxes(grid)))) == {
        "r0c0",
        "r0c1",
        "r0c2",
        "r1c0",
        "r1c1",
        "r1c2",
        "r2c0",
        "r2c1",
        "r2c2",
    }


@pytest.mark.parametrize("name", ["rows-distinct", "cols-distinct", "regions-distinct"])
def test_distinct_layer_requires_board(name: str) -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([LAYER_REGISTRY[name]])


@pytest.mark.parametrize("name", ["rows-distinct", "cols-distinct", "regions-distinct"])
def test_distinct_layer_emits_one_all_different_rule_per_group(
    name: str,
    assert_one_all_different_rule_per_group: Callable[[Engine], None],
) -> None:
    engine = build_engine([LAYER_REGISTRY["board"], LAYER_REGISTRY[name]])

    assert_one_all_different_rule_per_group(engine)
