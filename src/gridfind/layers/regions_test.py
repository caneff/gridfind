import pytest

from gridfind.engine import GridfindError
from gridfind.layers.regions import box_regions, region_map_for

BOARD_SIZE = 9


# Spelled out rather than read from BOX_SHAPE on purpose: an independent
# statement of the convention, so a typo in the table fails a test instead of
# being copied into the expectation.
@pytest.mark.parametrize(
    ("size", "box_rows", "box_cols"),
    [
        pytest.param(4, 2, 2, id="4x4-tiles-2x2"),
        pytest.param(6, 2, 3, id="6x6-tiles-2x3"),
        pytest.param(9, 3, 3, id="9x9-tiles-3x3"),
    ],
)
def test_box_regions_tiles_the_board_and_covers_every_cell_once(
    size: int, box_rows: int, box_cols: int
) -> None:
    # Every size tiles into `size` regions of `size` cells that partition the
    # board — a 6x6 as six 2x3 boxes, never as four 3x3 quattro quadri. The
    # coverage half is what a count-only assertion misses: a partition that
    # duplicated one cell and dropped another would still count right.
    region_map = box_regions(size, box_rows, box_cols)
    every_cell = [
        (row, col) for row in range(1, size + 1) for col in range(1, size + 1)
    ]

    assert len(region_map) == size
    for region in region_map:
        assert len(region) == size
    assert sorted(cell for region in region_map for cell in region) == every_cell


def test_region_map_for_falls_back_to_the_boards_box_tiling() -> None:
    # With no setter-supplied map, the box convention is the default source:
    # a 6x6 comes back tiled 2x3, R1C1's box holding its two rows of three.
    region_map = region_map_for(6)

    assert len(region_map) == 6
    assert region_map[0] == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]


def test_region_map_for_prefers_a_supplied_region_map() -> None:
    # A supplied map is the same region map from a different source, so it
    # passes through untouched — even at a size with no box convention.
    supplied = [[(1, 1), (1, 2)], [(2, 1), (2, 2)]]

    assert region_map_for(5, supplied) == supplied


def test_region_map_for_refuses_a_size_with_no_box_convention() -> None:
    # The refusal lives on the fallback: only a board asking to be tiled by
    # convention needs a convention to exist.
    with pytest.raises(GridfindError):
        region_map_for(5)
