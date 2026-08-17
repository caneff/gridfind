from hypothesis import given
from hypothesis import strategies as st

from gridfind.cell_geometry import format_address
from gridfind.sudokumaker.addresses import addresses, index_to_address


def test_index_to_address_translates_a_raw_index_row_major() -> None:
    assert index_to_address(18, size=9) == "R3C1"


@given(row=st.integers(1, 9), col=st.integers(1, 9))
def test_index_to_address_agrees_with_cell_geometry_for_every_cell(
    row: int, col: int
) -> None:
    index = (row - 1) * 9 + (col - 1)

    assert index_to_address(index, size=9) == format_address(row, col)


def test_addresses_maps_in_order_preserving_bulb_first_order() -> None:
    assert addresses([19, 18, 20], size=9) == ["R3C2", "R3C1", "R3C3"]
