import pytest
from hypothesis import given
from hypothesis import strategies as st

from gridfind.cell_geometry import (
    CellGeometry,
    cell_geometry,
    format_address,
)
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
    assert format_address(3, 1) == "R3C1"


def test_step_returns_the_target_cell_in_space() -> None:
    geometry = cell_geometry(Board(size=9))

    # A knight's hop: down 2, right 1.
    assert geometry.step("R1C1", 2, 1) == "R3C2"


def test_step_returns_none_stepping_off_the_declared_space() -> None:
    geometry = cell_geometry(Board(size=9))

    # Up 2 from row 1 leaves the space — no cell is declared at row -1.
    assert geometry.step("R1C1", -2, 1) is None


def test_step_from_an_undeclared_start_raises() -> None:
    geometry = cell_geometry(Board(size=4))

    with pytest.raises(KeyError):
        geometry.step("R9C9", 1, 0)


def _holed_geometry() -> CellGeometry:
    # A 3x3 address space with an interior hole: R2C2 is not declared. The hole
    # is what tells membership apart from a `1 <= row <= size` bounds check —
    # the cell-space contract that no full-board link can reach.
    grid = [
        ["R1C1", "R1C2", "R1C3"],
        ["R2C1", "R2C3"],
        ["R3C1", "R3C2", "R3C3"],
    ]
    return CellGeometry(size=3, values=range(1, 4), box_shape=None, grid=grid)


_HOLE = (2, 2)


@given(
    start=st.sampled_from(
        [
            (row, col)
            for row in range(1, 4)
            for col in range(1, 4)
            if (row, col) != _HOLE
        ]
    ),
    delta_row=st.integers(min_value=-3, max_value=3),
    delta_col=st.integers(min_value=-3, max_value=3),
)
def test_step_resolves_by_membership_not_a_bounds_check(
    start: tuple[int, int], delta_row: int, delta_col: int
) -> None:
    # The stepper answers from grid membership, not a `1 <= row <= size`
    # bounds check: over `_holed_geometry()`'s interior hole at R2C2, a
    # bounds-only implementation would wrongly resolve a step onto it, while
    # membership correctly reports None — the divergence a solid board can't
    # expose.
    geometry = _holed_geometry()
    declared = {address for line in geometry.grid for address in line}
    row, col = start

    target = geometry.step(format_address(row, col), delta_row, delta_col)

    in_space = format_address(row + delta_row, col + delta_col) in declared
    assert (target is not None) == in_space
    assert target is None or target in declared


def test_step_onto_an_interior_hole_is_off_space() -> None:
    # R2C2 sits inside 1..3 on both axes, so a bounds check would accept it;
    # membership rejects it because no cell is declared there.
    geometry = _holed_geometry()

    assert geometry.step("R1C2", 1, 0) is None


def test_step_resolves_a_present_cell_across_a_hole() -> None:
    # Stepping right from R2C1 skips the R2C2 hole and lands on the declared
    # R2C3 — position comes from the address, not a shifted list index.
    geometry = _holed_geometry()

    assert geometry.step("R2C1", 0, 2) == "R2C3"
