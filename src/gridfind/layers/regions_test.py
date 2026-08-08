import pytest

from gridfind.engine import GridfindError
from gridfind.layers.regions import (
    box_regions,
    classic_boxes,
    region_map_for,
    render_grid,
)

BOARD_SIZE = 9


def test_classic_region_map_partitions_the_board_into_boxes_of_boxes() -> None:
    region_map = classic_boxes()

    assert len(region_map) == BOARD_SIZE
    for region in region_map:
        assert len(region) == BOARD_SIZE


def test_classic_region_map_covers_every_cell_exactly_once() -> None:
    cells = [cell for region in classic_boxes() for cell in region]
    every_cell = {
        (row, col)
        for row in range(1, BOARD_SIZE + 1)
        for col in range(1, BOARD_SIZE + 1)
    }

    assert sorted(cells) == sorted(every_cell)


def test_box_region_map_at_9_3_3_reproduces_classic_region_map() -> None:
    # box_regions generalizes classic_boxes — at the classic board
    # size and box shape it must reproduce today's 3x3 partition exactly.
    assert box_regions(9, 3, 3) == classic_boxes()


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
def test_box_region_map_tiles_the_board_and_covers_every_cell_once(
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


def test_render_grid_bands_columns_and_rows_by_the_boards_box_shape() -> None:
    # A 6x6 tiles as 2x3 boxes (BOX_SHAPE[6]): a column gap every 3 cells, a
    # blank separator row every 2 rows — never the old fixed-3x3 banding.
    grid = [[f"R{r}C{c}" for c in range(1, 7)] for r in range(1, 7)]
    assignment = {name: i % 9 + 1 for i, row in enumerate(grid) for name in row}

    text = render_grid(grid, assignment)

    lines = text.split("\n")
    assert len(lines) == 8  # 6 rows plus two blank separator rows
    assert lines[2] == ""
    assert lines[5] == ""
    for line in lines:
        if line == "":
            continue
        left, right = line.split("  ")
        assert len(left.split(" ")) == 3
        assert len(right.split(" ")) == 3


def test_render_grid_renders_each_cells_own_value() -> None:
    # Size 3 has no classic box convention, so it renders as one ungrouped
    # block per row — this only probes the name-to-value substitution.
    grid = [
        ["R1C1", "R1C2", "R1C3"],
        ["R2C1", "R2C2", "R2C3"],
        ["R3C1", "R3C2", "R3C3"],
    ]
    assignment = {
        "R1C1": 4,
        "R1C2": 7,
        "R1C3": 9,
        "R2C1": 1,
        "R2C2": 2,
        "R2C3": 3,
        "R3C1": 5,
        "R3C2": 6,
        "R3C3": 8,
    }

    assert render_grid(grid, assignment) == "4 7 9\n1 2 3\n5 6 8"
