import pytest

from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import enumerate_witnesses, verdict
from gridfind.witness import Witness


def _pairwise_distinct(witnesses: tuple[Witness, ...]) -> bool:
    """True when no two witnesses are the same completion. A completion's
    identity is its full per-cell content — each cell's digit sequence (a
    widened S-cell's ordered pair, else its lone digit) and every discovered
    doubler (ADR-0015). Built here from the public `Witness` surface, so the
    check does not lean on how `verdict` keys distinctness inside."""
    identities = {
        (tuple(w.assignment.items()), tuple(w.modifiers.items())) for w in witnesses
    }
    return len(identities) == len(witnesses)


def _first_digit_grids(
    witnesses: tuple[Witness, ...],
) -> set[tuple[tuple[str, int], ...]]:
    """The set of distinct first-digit (`d0`) grids across the witnesses — what
    an identity keyed on `d0` alone would collapse them to. When this set is
    smaller than the witness count, two completions share every first digit yet
    count as distinct on their S-cell content or doubler placement."""
    return {
        tuple((address, content[0]) for address, content in w.assignment.items())
        for w in witnesses
    }


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


def test_blank_4x4_enumerates_all_288_completions_exhaustively() -> None:
    # The blank 4x4 sudoku has exactly 288 completions. A limit at or above the
    # true count returns every one, pairwise distinct, and reports the search
    # finished on its own. This is the exact-count / exhaustion check at a real
    # count, and it proves symmetric relabelings count as distinct: swapping all
    # 1s and 2s is one of the 288, folded away by no symmetry reasoning.
    blank = Puzzle(board=Board(size=4), constraints=(Constraint(type="sudoku"),))

    result = enumerate_witnesses(blank, limit=400)

    assert result.kind == "found"
    assert result.exhaustive is True
    assert len(result.witnesses) == 288
    assert _pairwise_distinct(result.witnesses)


def test_limit_below_true_count_truncates_and_is_not_exhaustive() -> None:
    # Asking for fewer than exist returns exactly that many distinct witnesses,
    # and `exhaustive` stays false so the caller never mistakes the first 100
    # for all 288.
    blank = Puzzle(board=Board(size=4), constraints=(Constraint(type="sudoku"),))

    result = enumerate_witnesses(blank, limit=100)

    assert result.kind == "found"
    assert result.exhaustive is False
    assert len(result.witnesses) == 100
    assert _pairwise_distinct(result.witnesses)


def test_s_cell_content_distinguishes_completions_sharing_a_first_digit_grid() -> None:
    # A 2x2 over {0,1,2} with one S-cell per row and per column has six
    # completions. Four distinct first-digit grids carry them: two grids each
    # hold two completions that share every first digit but place the S-cell on
    # the other cell of the line — same d0, different two-digit content. An
    # identity keyed on d0 alone merges each such pair into four; the full
    # identity keeps the S-cell pair and counts six (ADR-0015, story #10).
    s_puzzle = Puzzle(
        board=Board(size=2, values=range(3)),
        constraints=(
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="schrodinger"),
        ),
    )

    result = enumerate_witnesses(s_puzzle, limit=100)

    assert result.kind == "found"
    assert result.exhaustive is True
    assert len(result.witnesses) == 6
    assert _pairwise_distinct(result.witnesses)
    assert len(_first_digit_grids(result.witnesses)) == 4


def test_doubler_placement_distinguishes_completions_sharing_a_first_digit_grid() -> (
    None
):
    # A fully-given 4x4 sudoku grid fixes every digit, so every completion shares
    # one first-digit grid. The doubler is one per row, column, and box with all
    # digits different; this grid admits four such placements. Each is a distinct
    # completion on its modifier placement alone — an identity keyed on d0 alone
    # counts one (story #11).
    grid = ((1, 2, 3, 4), (3, 4, 1, 2), (2, 1, 4, 3), (4, 3, 2, 1))
    givens = tuple(
        Given(address=f"R{r + 1}C{c + 1}", digit=digit)
        for r, row in enumerate(grid)
        for c, digit in enumerate(row)
    )
    doubler_puzzle = Puzzle(
        board=Board(size=4),
        constraints=(Constraint(type="sudoku"), Constraint(type="doubler")),
        givens=givens,
    )

    result = enumerate_witnesses(doubler_puzzle, limit=100)

    assert result.kind == "found"
    assert result.exhaustive is True
    assert len(result.witnesses) == 4
    assert _pairwise_distinct(result.witnesses)
    assert len(_first_digit_grids(result.witnesses)) == 1
    assert len({tuple(w.modifiers.items()) for w in result.witnesses}) == 4


def test_mixed_s_cell_and_doubler_fixture_yields_distinct_witnesses() -> None:
    # A stack carrying both a schrodinger and a doubler layer. The identity spans
    # each cell's S-cell pair and each discovered doubler at once: the returned
    # witnesses are pairwise distinct, and the enumeration reaches both content
    # kinds — some witness holds an S-cell, some holds a doubler.
    mixed = Puzzle(
        board=Board(size=4, values=range(5)),
        constraints=(
            Constraint(type="sudoku"),
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
        ),
    )

    result = enumerate_witnesses(mixed, limit=8)

    assert result.kind == "found"
    assert len(result.witnesses) == 8
    assert _pairwise_distinct(result.witnesses)
    assert any(
        len(content) == 2
        for witness in result.witnesses
        for content in witness.assignment.values()
    )
    assert any(witness.modifiers for witness in result.witnesses)


@pytest.mark.slow
def test_mixed_s_cell_and_doubler_fixture_enumerates_all_17280_completions() -> None:
    # The full 4x4 sudoku + schrodinger + doubler stack has exactly 17280
    # completions, each counted on its S-cell content and doubler placement
    # together. Exhausting the whole space is a ~3s CP-SAT solve, so this pins
    # the exact mixed-stack count on demand (`just slow`) rather than every gate.
    mixed = Puzzle(
        board=Board(size=4, values=range(5)),
        constraints=(
            Constraint(type="sudoku"),
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
        ),
    )

    result = enumerate_witnesses(mixed, limit=20000, time_limit_s=120.0)

    assert result.kind == "found"
    assert result.exhaustive is True
    assert len(result.witnesses) == 17280
    assert _pairwise_distinct(result.witnesses)
