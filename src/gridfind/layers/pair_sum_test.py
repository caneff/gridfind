"""pair-sum behaviour, tested at the top seam — `verdict` (issue #66).

The canonical `pair-sum` clue names a pair and its target; the XV variant rides
on top as sugar — a `v` clue is a pair-sum of 5, an `x` clue a pair-sum of 10.
"""

from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _pair_sum(cells: tuple[str, str], total: int) -> Constraint:
    return Constraint(type="pair-sum", params={"cells": list(cells), "sum": total})


def _clue(kind: str, cells: tuple[str, str]) -> Constraint:
    """An X or V sugar clue — names its pair, leaves the sum to the sugar."""
    return Constraint(type=kind, params={"cells": list(cells)})


def test_a_satisfiable_pair_resolves_found() -> None:
    puzzle = Puzzle(board=BOARD, constraints=(_pair_sum(("R1C1", "R1C2"), 5),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] + result.witness["R1C2"] == 5


def test_a_pair_that_cannot_meet_its_sum_resolves_broke() -> None:
    # Both cells pinned to 1 (sum 2) — a pair-sum wanting 5 has no completion.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_sum(("R1C1", "R1C2"), 5),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_clues_each_constrain_their_own_pair_independently() -> None:
    # One pair-sum layer, two rules (the dedup-by-type path): each given fixes
    # one cell of its clue, so each clue must force its own partner.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_sum(("R1C1", "R1C2"), 5), _pair_sum(("R3C3", "R3C4"), 10)),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=6)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"] == 4  # 1 + 4 == 5
    assert result.witness["R3C4"] == 4  # 6 + 4 == 10


def test_a_broken_second_clue_breaks_the_whole_puzzle() -> None:
    # Independence in the breaking direction: the first clue is satisfiable, the
    # second cannot meet its sum — proof the second rule is really emitted.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_pair_sum(("R1C1", "R1C2"), 5), _pair_sum(("R3C3", "R3C4"), 10)),
        givens=(Given(address="R3C3", digit=1), Given(address="R3C4", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_v_clue_is_sugar_for_a_pair_sum_of_five() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_clue("v", ("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=3),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"] == 2  # V binds the pair to 5


def test_an_x_clue_is_sugar_for_a_pair_sum_of_ten() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_clue("x", ("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=3),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"] == 7  # X binds the pair to 10
