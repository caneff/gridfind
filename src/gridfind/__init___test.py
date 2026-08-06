from gridfind import Puzzle, Verdict, WorkingState, verdict
from gridfind.puzzle import Board, Given


def test_public_api_exposes_verdict_end_to_end() -> None:
    puzzle = Puzzle(board=Board(size=9), givens=(Given(address="R1C1", digit=5),))
    result = verdict(puzzle, WorkingState())

    assert isinstance(result, Verdict)
    assert result.kind == "found"
