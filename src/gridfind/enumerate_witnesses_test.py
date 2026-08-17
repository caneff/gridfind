from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.sudokumaker import link_to_puzzle
from gridfind.verdict import Enumeration, enumerate_witnesses
from gridfind.witness import Witness, WitnessIdentity

_LINKS_DIR = Path(__file__).parent / "links"


def _mixed_stack_puzzle() -> Puzzle:
    """The 4x4 sudoku + schrodinger + doubler stack. Its 17280 completions are
    far more than any tight time budget can enumerate, so it drives the
    phase-2-timeout path: the search always finds some and never exhausts."""
    return Puzzle(
        board=Board(size=4, values=range(5)),
        constraints=(
            Constraint(type="sudoku"),
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
        ),
    )


def _identity_set(result: Enumeration) -> set[WitnessIdentity]:
    """The set of witness identities in a result — each witness's per-cell
    content and discovered doublers (ADR-0015), the same identity `verdict`
    dedups on. Built from the public `Witness.identity` so the check does not
    lean on how the enumeration keys distinctness inside."""
    return {w.identity for w in result.witnesses}


def _pairwise_distinct(witnesses: tuple[Witness, ...]) -> bool:
    """True when no two witnesses are the same completion. A completion's
    identity is its full per-cell content — each cell's digit sequence (a
    widened S-cell's ordered pair, else its lone digit) and every discovered
    doubler (ADR-0015). Built here from the public `Witness.identity`, so the
    check does not lean on how `verdict` keys distinctness inside."""
    identities = {w.identity for w in witnesses}
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


def test_exactly_two_puzzle_returns_two_distinct_exhaustive_witnesses() -> None:
    # A one-cell board over {1, 2} with nothing to pin it has exactly two
    # completions.
    puzzle = Puzzle(board=Board(size=1, values=range(1, 3)))

    result = enumerate_witnesses(puzzle, limit=5)

    assert result.kind == "found"
    assert len(result.witnesses) == 2
    assert result.exhaustive is True
    assert result.witnesses[0]["R1C1"] != result.witnesses[1]["R1C1"]


def test_infeasible_puzzle_breaks_with_no_witnesses() -> None:
    puzzle = _over_large_region_puzzle()

    result = enumerate_witnesses(puzzle, limit=5)

    assert result.kind == "broke"
    assert result.witnesses == ()


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
    # identity keeps the S-cell pair and counts six (ADR-0015).
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
    # counts one.
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


def test_phase_two_timeout_returns_partial_witnesses_not_exhaustive() -> None:
    # Phase 1 finds, so phase 2 runs; with a limit far above the true count the
    # search can only stop on the clock, not the limit. A budget too small to
    # enumerate all 17280 completions returns the ones found so far with
    # `exhaustive=False` — the caller keeps the partial set and knows more
    # exist. The budget has wide margin either way: phase 1 is one fast
    # feasibility solve, and exhausting 17280 single-worker takes seconds, so
    # 0.5s reliably finds some and never all. The count itself is
    # timing-dependent, so the assertion pins the contract, not a number.
    result = enumerate_witnesses(_mixed_stack_puzzle(), limit=20001, time_limit_s=0.5)

    assert result.kind == "found"
    assert result.exhaustive is False
    assert 0 < len(result.witnesses) < 17280
    assert _pairwise_distinct(result.witnesses)


def test_phase_one_timeout_with_nothing_found_returns_unknown_empty() -> None:
    # A zero-second budget lets phase 1 do no work, so it decides nothing and
    # returns `unknown` with an empty tuple — distinct from `broke`, which
    # proves no completion exists. Zero seconds models the
    # phase-1-exhausted-the-budget case with no dependence on machine speed: no
    # solve can finish in zero time.
    result = enumerate_witnesses(_mixed_stack_puzzle(), limit=5, time_limit_s=0.0)

    assert result.kind == "unknown"
    assert result.witnesses == ()
    assert result.exhaustive is False


@settings(max_examples=25, deadline=None)
@given(
    size=st.integers(min_value=1, max_value=2),
    domain=st.integers(min_value=1, max_value=3),
    limit=st.integers(min_value=1, max_value=12),
)
def test_witnesses_are_pairwise_distinct_and_within_limit(
    size: int, domain: int, limit: int
) -> None:
    # For any small board and limit, the returned witnesses are pairwise
    # distinct and number at most `limit`. An unconstrained board
    # has domain**cells completions, always feasible, so every draw returns
    # `found` and exercises both truncation (limit below the count) and
    # exhaustion (limit at or above it).
    puzzle = Puzzle(board=Board(size=size, values=range(1, domain + 1)))

    result = enumerate_witnesses(puzzle, limit=limit)

    assert result.kind == "found"
    assert len(result.witnesses) <= limit
    assert _pairwise_distinct(result.witnesses)


@settings(max_examples=20, deadline=None)
@given(
    size=st.integers(min_value=1, max_value=2),
    domain=st.integers(min_value=1, max_value=3),
)
def test_exhaustive_result_is_stable_under_higher_limit(size: int, domain: int) -> None:
    # When `exhaustive` is True, the enumeration saw every completion, so
    # re-running with a higher limit returns the same set and the same count.
    # A generous first limit reaches exhaustion on these small
    # boards; the rare draw whose true count exceeds it is dropped by `assume`.
    puzzle = Puzzle(board=Board(size=size, values=range(1, domain + 1)))

    first = enumerate_witnesses(puzzle, limit=64)
    assume(first.exhaustive)

    again = enumerate_witnesses(puzzle, limit=128)

    assert again.exhaustive is True
    assert len(again.witnesses) == len(first.witnesses)
    assert _identity_set(again) == _identity_set(first)


@pytest.mark.e2e
def test_real_link_multi_witness_enumeration_through_the_library_path() -> None:
    # The library path end to end on a real SudokuMaker link: decode the corpus
    # kropki 4x4, which has exactly 12 completions, and enumerate them. A limit
    # above the count returns all 12, exhaustively and pairwise distinct; a
    # limit below truncates to that many and reports the search unfinished. The
    # CLI front door is out of scope here — this drives `enumerate_witnesses`
    # directly.
    link = (_LINKS_DIR / "found-kropki-4x4.txt").read_text().split()[-1]
    puzzle, working_state = link_to_puzzle(link)

    full = enumerate_witnesses(puzzle, working_state, limit=50)
    assert full.kind == "found"
    assert full.exhaustive is True
    assert len(full.witnesses) == 12
    assert _pairwise_distinct(full.witnesses)

    truncated = enumerate_witnesses(puzzle, working_state, limit=5)
    assert truncated.exhaustive is False
    assert len(truncated.witnesses) == 5
    assert _pairwise_distinct(truncated.witnesses)
