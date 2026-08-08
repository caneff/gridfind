from gridfind.layers.board import BOARD_SIZE
from gridfind.layers.regions import classic_region_map, render_grid


def test_classic_region_map_partitions_the_board_into_boxes_of_boxes() -> None:
    region_map = classic_region_map()

    assert len(region_map) == BOARD_SIZE
    for region in region_map:
        assert len(region) == BOARD_SIZE


def test_classic_region_map_covers_every_cell_exactly_once() -> None:
    cells = [cell for region in classic_region_map() for cell in region]
    every_cell = {
        (row, col)
        for row in range(1, BOARD_SIZE + 1)
        for col in range(1, BOARD_SIZE + 1)
    }

    assert sorted(cells) == sorted(every_cell)


def test_classic_region_map_scales_to_other_board_sizes() -> None:
    # Size-agnostic: a 6x6 board cut into 3x3 boxes gives four regions of nine.
    region_map = classic_region_map(board_size=6)

    assert len(region_map) == 4
    for region in region_map:
        assert len(region) == 9


def test_render_grid_bands_columns_and_rows_by_region_size() -> None:
    # A 6x6 grid so region banding (3) shows twice in each direction.
    grid = [[f"R{r}C{c}" for c in range(1, 7)] for r in range(1, 7)]
    values = {name: i % 9 + 1 for i, row in enumerate(grid) for name in row}

    text = render_grid(grid, values)

    lines = text.split("\n")
    assert len(lines) == 7  # 6 rows plus one blank separator row
    assert lines[3] == ""  # the separator between the two region row-bands
    # Each rendered row groups its six digits into two 3-digit clusters,
    # joined by the double space that marks a region-column boundary.
    for line in (lines[0], lines[1], lines[2], lines[4], lines[5], lines[6]):
        left, right = line.split("  ")
        assert len(left.split(" ")) == 3
        assert len(right.split(" ")) == 3


def test_render_grid_renders_each_cells_own_value() -> None:
    grid = [["R1C1", "R1C2", "R1C3"]]
    values = {"R1C1": 4, "R1C2": 7, "R1C3": 9}

    assert render_grid(grid, values) == "4 7 9"
