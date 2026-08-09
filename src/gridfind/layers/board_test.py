import pytest

from gridfind.engine import build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import cell_values
from gridfind.puzzle import Board


@pytest.mark.parametrize("size", [4, 6, 9])
def test_board_registers_every_grid_cell_with_rxcy_addressing(size: int) -> None:
    engine = build_engine([GridCells()], board=Board(size=size))

    assert len(engine.cells) == size * size
    assert set(engine.cells) == {
        f"R{r}C{c}" for r in range(1, size + 1) for c in range(1, size + 1)
    }
    for cell in engine.cells.values():
        assert len(cell.content) == 1


@pytest.mark.parametrize("size", [4, 6, 9])
def test_board_bounds_every_cell_to_the_boards_own_values(
    size: int,
) -> None:
    engine = build_engine([GridCells()], board=Board(size=size))

    for address in engine.cells:
        assert cell_values(engine, address) == list(range(1, size + 1))


def test_board_bounds_cells_to_values_a_setter_chose_over_the_size_default() -> None:
    """A setter's own values, not the size default — every cell offers 0-3."""
    board = Board(size=4, values=range(4))

    engine = build_engine([GridCells()], board=board)

    for address in engine.cells:
        assert cell_values(engine, address) == [0, 1, 2, 3]
