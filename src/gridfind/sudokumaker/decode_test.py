"""`link_to_puzzle`: the whole-assembly decode from a classic SudokuMaker link to
gridfind's `Puzzle` + `WorkingState`.
"""

from gridfind.puzzle import Board, Candidate, Given, Placement, Puzzle, WorkingState
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import CLASSIC_CONSTRAINTS


def test_classic_link_decodes_to_expected_puzzle_and_state(classic_link: str) -> None:
    puzzle, state = link_to_puzzle(classic_link)

    assert puzzle == Puzzle(
        board=Board(size=9),
        constraints=CLASSIC_CONSTRAINTS,
        givens=(
            Given("R1C6", 4),
            Given("R4C3", 5),
            Given("R7C2", 6),
            Given("R7C6", 8),
        ),
    )
    # R6C8's single center mark `candidates 4 = 2^2` is a one-digit narrowing,
    # so it lands as a Candidate, never a Placement — the exact-state equality
    # below pins that (R6C8 is in candidates and absent from places).
    assert state == WorkingState(
        places=(Placement("R1C1", 7),),
        candidates=(
            Candidate("R2C9", frozenset({1, 2, 9})),
            Candidate("R6C8", frozenset({2})),
        ),
    )
