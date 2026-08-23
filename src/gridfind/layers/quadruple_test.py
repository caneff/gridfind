"""`quadruple` behaviour, tested at the seams the issue names: `verdict`
(mirroring `parity_test.py`) for the plain found/broke pairs, and the
existential-presence shape a quadruple clue rests on — a required digit may
sit in *any* one of its four cells, not a fixed one.
"""

from __future__ import annotations

from gridfind.engine import build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.quadruple import Quadruple
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)
_CELLS = ("R1C1", "R1C2", "R2C1", "R2C2")


def _quadruple(digits: tuple[int, ...]) -> Constraint:
    return Constraint(
        "quadruple", params={"cells": list(_CELLS), "digits": list(digits)}
    )


def test_no_quadruple_constraint_emits_nothing() -> None:
    bare = build_engine([GridCells()], board=BOARD)
    with_layer = build_engine([GridCells(), Quadruple()], board=BOARD)

    assert len(with_layer.model.proto.constraints) == len(bare.model.proto.constraints)


def test_a_satisfiable_quadruple_clue_resolves_found_with_a_witness() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_quadruple((1, 2)),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"][0] == 1
    assert result.witness["R1C2"][0] == 2


def test_a_required_digit_missing_from_every_cell_resolves_broke() -> None:
    # Every one of the four cells is pinned away from digit 3 — the clue
    # requires 3 to appear somewhere in the block, so no assignment satisfies
    # it regardless of the rest of the board.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_quadruple((3,)),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=2),
            Given(address="R2C1", digit=4),
            Given(address="R2C2", digit=5),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_required_digit_may_sit_in_any_one_of_the_four_cells() -> None:
    # Three of the four cells are pinned away from digit 3; only the fourth
    # (R2C2) is left free to carry it — presence, not a fixed position.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_quadruple((3,)),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=2),
            Given(address="R2C1", digit=4),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R2C2"][0] == 3
