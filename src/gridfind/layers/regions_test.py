from gridfind.layers.board import BOARD_SIZE
from gridfind.layers.regions import classic_region_map


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
