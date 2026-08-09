import pytest
from ortools.sat.python import cp_model

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


@pytest.mark.parametrize("digit", [3, 5, 7])
def test_board_excludes_a_digit_between_a_stepped_domains_gaps(digit: int) -> None:
    """A board declaring 2, 4, 6, 8 must exclude 3, 5, 7 — the regression the
    issue names. Bounding a cell to the domain's two ends is not enough: a
    digit strictly between two declared values is illegal, so forcing one
    onto the cell must be infeasible."""
    board = Board(size=1, values=range(2, 9, 2))
    engine = build_engine([GridCells()], board=board)
    var = engine.cells["R1C1"].content[0]
    engine.model.add(var == digit)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


@pytest.mark.parametrize("digit", [2, 4, 6, 8])
def test_board_admits_every_declared_digit_in_a_stepped_domain(digit: int) -> None:
    """The other half of the regression fix: excluding the gaps must not
    exclude the declared values themselves."""
    board = Board(size=1, values=range(2, 9, 2))
    engine = build_engine([GridCells()], board=board)
    var = engine.cells["R1C1"].content[0]
    engine.model.add(var == digit)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
