"""`window-groups` behaviour at the verdict seam, mirroring
`line_test.py`'s grouped-line coverage: no structural readback helper (the
rule reads group membership over a 2x2 window, not addresses), so coverage
sits at direct-model / verdict behaviour. Each puzzle carries only the
`window-groups` constraint itself, no sudoku rows/cols/regions-distinct — the
same minimal posture `line_test.py`'s grouped-line tests take — so the
verdict turns on the rule under test alone.
"""

from __future__ import annotations

import pytest

from gridfind.engine import GridfindError, MalformedPuzzleError
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=4)


def _mask(*digits: int) -> int:
    mask = 0
    for digit in digits:
        mask |= 1 << digit
    return mask


LOW_HIGH_GROUPS = [_mask(1, 2), _mask(3, 4)]


def _window_groups(groups: list[int]) -> Constraint:
    return Constraint("window-groups", params={"groups": groups})


def test_a_window_hitting_every_group_resolves_found() -> None:
    # R1C1 (low) and R2C2 (high) alone already satisfy both groups; R1C2 and
    # R2C1 are left free.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_window_groups(LOW_HIGH_GROUPS),),
        givens=(Given(address="R1C1", digit=1), Given(address="R2C2", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_a_window_missing_a_group_resolves_broke() -> None:
    # All four window cells given, every one from the low group — the high
    # group has no member present, unsatisfiable once the rule is added.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_window_groups(LOW_HIGH_GROUPS),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=2),
            Given(address="R2C1", digit=2),
            Given(address="R2C2", digit=1),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_window_groups_clues_are_both_enforced() -> None:
    # Entropy (low/high) plus a second, independent parity-flavoured clue on
    # the same window: R1C1=1 is low and odd, R2C2=3 is high and odd, so the
    # even group has no member present — broke on the second clue alone.
    parity_groups = [_mask(1, 3), _mask(2, 4)]
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _window_groups(LOW_HIGH_GROUPS),
            _window_groups(parity_groups),
        ),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=3),
            Given(address="R2C1", digit=1),
            Given(address="R2C2", digit=3),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"


def test_empty_groups_raises() -> None:
    puzzle = Puzzle(board=BOARD, constraints=(_window_groups([]),))

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


def test_a_gap_in_groups_is_honored_not_refused() -> None:
    # Only digit 1 is named; 2, 3, 4 form a gap grouped-line's strict
    # validate_partition would refuse. R1C1=1 satisfies the sole group; the
    # gapped digits on the other three cells carry no rule of their own.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_window_groups([_mask(1)]),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=2),
            Given(address="R2C1", digit=3),
            Given(address="R2C2", digit=4),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_an_overlap_in_groups_is_honored_not_refused() -> None:
    # Digit 2 sits in both groups — an overlap grouped-line's strict
    # validate_partition would refuse. A single cell holding 2 satisfies
    # both groups at once.
    overlapping_groups = [_mask(1, 2), _mask(2, 3)]
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_window_groups(overlapping_groups),),
        givens=(
            Given(address="R1C1", digit=2),
            Given(address="R1C2", digit=4),
            Given(address="R2C1", digit=4),
            Given(address="R2C2", digit=4),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_a_multi_slot_schrodinger_cell_under_window_groups_raises() -> None:
    # Window-groups is window-structured like grouped-line: a Schrödinger-
    # widened cell has no defined single-window fold, so it refuses loud
    # (via `sole`, engine.py) rather than guess one.
    board = Board(size=4, values=range(5))
    groups = [_mask(0, 1), _mask(2, 3, 4)]
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            _window_groups(groups),
        ),
    )

    with pytest.raises(GridfindError):
        verdict(puzzle)
