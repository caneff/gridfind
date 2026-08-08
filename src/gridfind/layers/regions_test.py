from gridfind.layers.regions import box_region_map, classic_region_map, render_grid

BOARD_SIZE = 9


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


def test_box_region_map_at_9_3_3_reproduces_classic_region_map() -> None:
    # box_region_map generalizes classic_region_map — at the classic board
    # size and box shape it must reproduce today's 3x3 partition exactly.
    assert box_region_map(9, 3, 3) == classic_region_map()


def test_box_region_map_tiles_a_6x6_into_six_2x3_boxes() -> None:
    # A genuine 6x6 tiles as six 2x3 boxes, never as four 3x3 quattro quadri.
    region_map = box_region_map(6, 2, 3)

    assert len(region_map) == 6
    for region in region_map:
        assert len(region) == 6


def test_box_region_map_tiles_a_4x4_into_four_2x2_boxes() -> None:
    region_map = box_region_map(4, 2, 2)

    assert len(region_map) == 4
    for region in region_map:
        assert len(region) == 4


def test_box_region_map_covers_every_cell_exactly_once_at_6x6() -> None:
    cells = [cell for region in box_region_map(6, 2, 3) for cell in region]
    every_cell = {(row, col) for row in range(1, 7) for col in range(1, 7)}

    assert sorted(cells) == sorted(every_cell)


def test_render_grid_bands_columns_and_rows_by_the_boards_box_shape() -> None:
    # A 6x6 tiles as 2x3 boxes (BOX_SHAPE[6]): a column gap every 3 cells, a
    # blank separator row every 2 rows — never the old fixed-3x3 banding.
    grid = [[f"R{r}C{c}" for c in range(1, 7)] for r in range(1, 7)]
    values = {name: i % 9 + 1 for i, row in enumerate(grid) for name in row}

    text = render_grid(grid, values)

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
    values = {
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

    assert render_grid(grid, values) == "4 7 9\n1 2 3\n5 6 8"
