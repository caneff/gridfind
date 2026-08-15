import pytest

from gridfind.puzzle import Board, Constraint, Puzzle
from gridfind.verdict import enumerate_witnesses, verdict


def _over_large_region_puzzle() -> Puzzle:
    # A region larger than the digit domain is unsolvable by pigeonhole.
    labels = [0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 3, 3, 2, 2, 3, 3]
    return Puzzle(
        board=Board(size=4),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct", params={"regions": labels}),
        ),
    )


def test_unique_puzzle_returns_one_exhaustive_witness() -> None:
    # A one-cell board over the single digit {1} has exactly one completion.
    puzzle = Puzzle(board=Board(size=1))

    result = enumerate_witnesses(puzzle, limit=5)

    assert result.kind == "found"
    assert len(result.witnesses) == 1
    assert result.exhaustive is True
    assert result.reason is None


def test_exactly_two_puzzle_returns_two_distinct_exhaustive_witnesses() -> None:
    # A one-cell board over {1, 2} with nothing to pin it has exactly two
    # completions.
    puzzle = Puzzle(board=Board(size=1, values=range(1, 3)))

    result = enumerate_witnesses(puzzle, limit=5)

    assert result.kind == "found"
    assert len(result.witnesses) == 2
    assert result.exhaustive is True
    assert result.witnesses[0]["R1C1"] != result.witnesses[1]["R1C1"]


def test_infeasible_puzzle_breaks_with_the_verdict_reason() -> None:
    puzzle = _over_large_region_puzzle()

    result = enumerate_witnesses(puzzle, limit=5)

    assert result.kind == "broke"
    assert result.witnesses == ()
    assert result.reason == verdict(puzzle).reason
    assert result.reason is not None


def test_limit_zero_raises() -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        enumerate_witnesses(Puzzle(board=Board(size=1)), limit=0)
