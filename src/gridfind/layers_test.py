import pytest

from gridfind.engine import MissingDependencyError, build_engine
from gridfind.layers import BOARD_SIZE, UnknownLayerError, resolve


def test_board_registers_every_grid_cell_with_rxcy_addressing():
    (board,) = resolve(["board"])
    engine = build_engine([board])

    assert len(engine.cells) == BOARD_SIZE * BOARD_SIZE
    assert set(engine.cells) == {
        f"R{r}C{c}" for r in range(1, BOARD_SIZE + 1) for c in range(1, BOARD_SIZE + 1)
    }
    for cell in engine.cells.values():
        assert len(cell.content) == 1


def test_board_emits_no_rules():
    (board,) = resolve(["board"])
    engine = build_engine([board])

    assert len(engine.model.proto.constraints) == 0


def test_resolve_rejects_an_unregistered_layer_name():
    with pytest.raises(UnknownLayerError):
        resolve(["not-a-real-layer"])


def test_rows_distinct_requires_board():
    (rows_distinct,) = resolve(["rows-distinct"])

    with pytest.raises(MissingDependencyError):
        build_engine([rows_distinct])


def test_rows_distinct_emits_one_all_different_rule_per_row():
    engine = build_engine(resolve(["board", "rows-distinct"]))

    assert len(engine.model.proto.constraints) == BOARD_SIZE
    for constraint in engine.model.proto.constraints:
        assert constraint.has_all_diff()
        assert len(constraint.all_diff.exprs) == BOARD_SIZE
