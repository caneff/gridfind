"""group-sum behaviour, tested at two seams (issue #241, spec #240).

group-sum is purely additive: an N-ary sum reduction over a named set of
cells, S-blind, carrying no implied uniqueness. `pair-sum` and `cage` are
untouched here — this only proves the new layer's own behaviour, mirroring
`pair_sum_test.py` and the killer-sum half of `cage_test.py`.

Most of it is behaviour at the top seam — `verdict`: a clue's effect on the
completion, including the bare-repeat and S-cell-raise cases the spec calls
out by name. The rule the layer emits is also read back directly (issue
#100), the one claim a solve cannot make: that a clue emitted its *own* rule
rather than being satisfied by accident, and that no `add_all_different`
rides along with it.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gridfind.engine import GridfindError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import all_different_groups, pair_sum_rules
from gridfind.layers.group_sum import GroupSum
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _group_sum(cells: tuple[str, ...], total: int) -> Constraint:
    return Constraint(type="group-sum", params={"cells": list(cells), "sum": total})


def test_group_sum_emits_one_rule_per_clue() -> None:
    constraints = (
        _group_sum(("R1C1", "R1C2"), 5),
        _group_sum(("R3C3", "R3C4", "R3C5"), 12),
    )
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert pair_sum_rules(engine) == [
        (["R1C1", "R1C2"], 5),
        (["R3C3", "R3C4", "R3C5"], 12),
    ]


def test_group_sum_emits_no_all_different_rule() -> None:
    # The "total only" decision: a group-sum never adds distinctness pressure.
    puzzle = Puzzle(board=BOARD, constraints=(_group_sum(("R1C1", "R1C2"), 5),))
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert all_different_groups(engine) == []


def test_no_group_sum_constraint_emits_nothing() -> None:
    engine = build_engine([GridCells(), GroupSum()], board=BOARD)

    assert pair_sum_rules(engine) == []


def test_a_satisfiable_group_sum_resolves_found() -> None:
    puzzle = Puzzle(board=BOARD, constraints=(_group_sum(("R1C1", "R1C2"), 5),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"][0] + result.witness["R1C2"][0] == 5


def test_a_three_cell_group_sum_resolves_found_with_a_witness_summing_to_it() -> None:
    # The any-arity story: two cells is just the smallest case.
    cells = ("R1C1", "R1C2", "R1C3")
    puzzle = Puzzle(board=BOARD, constraints=(_group_sum(cells, 12),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert sum(result.witness[address][0] for address in cells) == 12


def test_a_group_sum_that_cannot_meet_its_total_resolves_broke() -> None:
    # Two cells on a 1-9 board can reach at most 18; 30 is unreachable.
    puzzle = Puzzle(board=BOARD, constraints=(_group_sum(("R1C1", "R1C2"), 30),))

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_bare_group_sum_permits_a_repeat_among_its_cells() -> None:
    # A non-house pair summing to 10 admits 5+5 — no uniqueness rides along
    # with a bare group-sum.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_group_sum(("R1C1", "R1C2"), 10),),
        givens=(Given(address="R1C1", digit=5),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 5


def test_two_group_sums_each_constrain_their_own_cells_independently() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _group_sum(("R1C1", "R1C2"), 5),
            _group_sum(("R3C3", "R3C4"), 10),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=6)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 4  # 1 + 4 == 5
    assert result.witness["R3C4"][0] == 4  # 6 + 4 == 10


def test_a_broken_second_group_sum_breaks_the_whole_puzzle() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _group_sum(("R1C1", "R1C2"), 5),
            _group_sum(("R3C3", "R3C4"), 10),
        ),
        givens=(Given(address="R3C3", digit=1), Given(address="R3C4", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_group_sum_over_a_widened_cell_raises_not_schrodinger_ready() -> None:
    # The sum reads through singular `content()` (`sole`), which raises the
    # moment an S-cell is possible — S-blind by decision, matching the
    # cage's killer sum.
    with pytest.raises(GridfindError, match="not Schrödinger-ready"):
        build_engine(
            [GridCells(), Schrodinger(), GroupSum()],
            (_group_sum(("R1C1", "R1C2"), 3),),
            board=Board(size=4, values=range(5)),
        )


def test_a_plain_sudoku_with_no_group_sum_clue_is_unaffected() -> None:
    # No-regression: a stack that never sees a group-sum clue adds no rule,
    # and an ordinary sudoku still resolves as before.
    puzzle = Puzzle(board=BOARD, constraints=(Constraint(type="sudoku"),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness) == 81


def _row_cells(count: int) -> list[str]:
    return [f"R1C{column}" for column in range(1, count + 1)]


@given(count=st.integers(min_value=2, max_value=9), total=st.integers(-20, 100))
@settings(max_examples=50)
def test_group_sum_reachability_matches_its_arity_at_any_n(
    count: int, total: int
) -> None:
    # Values 1-9, count cells, repeats allowed (no other rule): reachable
    # totals span [count, 9 * count] exactly.
    cells = _row_cells(count)
    puzzle = Puzzle(board=BOARD, constraints=(_group_sum(tuple(cells), total),))

    result = verdict(puzzle)

    if count <= total <= 9 * count:
        assert result.kind == "found"
        assert result.witness is not None
        assert sum(result.witness[address][0] for address in cells) == total
    else:
        assert result.kind == "broke"
        assert result.witness is None
