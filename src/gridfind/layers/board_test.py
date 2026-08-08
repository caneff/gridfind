import pytest

from gridfind.engine import build_engine
from gridfind.layers import LAYER_REGISTRY
from gridfind.puzzle import Board


@pytest.mark.parametrize("size", [4, 6, 9])
def test_board_registers_every_grid_cell_with_rxcy_addressing(size: int) -> None:
    engine = build_engine([LAYER_REGISTRY["board"]], board=Board(size=size))

    assert len(engine.cells) == size * size
    assert set(engine.cells) == {
        f"R{r}C{c}" for r in range(1, size + 1) for c in range(1, size + 1)
    }
    for cell in engine.cells.values():
        assert len(cell.content) == 1


@pytest.mark.parametrize("size", [4, 6, 9])
def test_board_bounds_every_cell_to_the_boards_own_values(size: int) -> None:
    engine = build_engine([LAYER_REGISTRY["board"]], board=Board(size=size))

    for cell in engine.cells.values():
        domain = list(cell.content[0].proto.domain)
        assert (domain[0], domain[-1]) == (1, size)


def test_board_bounds_cells_to_values_a_setter_chose_over_the_size_default() -> None:
    board = Board(size=4, values=range(4))

    engine = build_engine([LAYER_REGISTRY["board"]], board=board)

    for cell in engine.cells.values():
        domain = list(cell.content[0].proto.domain)
        assert (domain[0], domain[-1]) == (0, 3)


def test_board_emits_no_rules() -> None:
    engine = build_engine([LAYER_REGISTRY["board"]], board=Board(size=9))

    assert len(engine.model.proto.constraints) == 0
