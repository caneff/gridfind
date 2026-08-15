import pytest

from gridfind.cell_geometry import BOX_SHAPE, cell_address, cell_geometry
from gridfind.puzzle import Board


def test_cell_geometry_holds_the_boards_size_and_values() -> None:
    board = Board(size=4)

    geometry = cell_geometry(board)

    assert geometry.size == 4
    assert geometry.values == range(1, 5)


def test_cell_geometry_holds_a_setters_own_values() -> None:
    board = Board(size=4, values=range(4))

    geometry = cell_geometry(board)

    assert geometry.values == range(4)


@pytest.mark.parametrize(
    ("size", "shape"), [(4, (2, 2)), (6, (2, 3)), (9, (3, 3))], ids=["4", "6", "9"]
)
def test_cell_geometry_box_shape_matches_the_classic_convention(
    size: int, shape: tuple[int, int]
) -> None:
    geometry = cell_geometry(Board(size=size))

    assert geometry.box_shape == shape


def test_cell_geometry_box_shape_is_none_with_no_classic_convention() -> None:
    geometry = cell_geometry(Board(size=5))

    assert geometry.box_shape is None


def test_cell_geometry_grid_is_the_row_major_rxcy_address_grid() -> None:
    geometry = cell_geometry(Board(size=3))

    assert geometry.grid == [
        ["R1C1", "R1C2", "R1C3"],
        ["R2C1", "R2C2", "R2C3"],
        ["R3C1", "R3C2", "R3C3"],
    ]


def test_cell_address_formats_rxcy() -> None:
    assert cell_address(3, 1) == "R3C1"


def test_box_shape_table_matches_regions_layers_convention() -> None:
    # `cell_geometry`'s `box_shape` and `layers.regions.region_map_for`'s
    # fallback tiling must agree on every classic size — both read this one
    # table (ADR-0004).
    assert BOX_SHAPE == {4: (2, 2), 6: (2, 3), 9: (3, 3)}
