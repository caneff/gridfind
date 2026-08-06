from gridfind.engine import build_engine
from gridfind.layers import resolve
from gridfind.layers.board import BOARD_SIZE


def test_board_registers_every_grid_cell_with_rxcy_addressing() -> None:
    (board,) = resolve(["board"])
    engine = build_engine([board])

    assert len(engine.cells) == BOARD_SIZE * BOARD_SIZE
    assert set(engine.cells) == {
        f"R{r}C{c}" for r in range(1, BOARD_SIZE + 1) for c in range(1, BOARD_SIZE + 1)
    }
    for cell in engine.cells.values():
        assert len(cell.content) == 1


def test_board_emits_no_rules() -> None:
    (board,) = resolve(["board"])
    engine = build_engine([board])

    assert len(engine.model.proto.constraints) == 0
