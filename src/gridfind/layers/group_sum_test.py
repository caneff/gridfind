"""group-sum behaviour, tested at two seams.

group-sum is purely additive: an N-ary sum reduction over a named set of
cells, carrying no implied uniqueness. This file proves this layer's own
behaviour; a killer cage composing it with `cage`'s no-repeats rule is tested
at the `verdict` seam in `verdict_test.py`.

The `x`/`v` aliases resolve onto this layer too, each fixing a two-cell
group-sum's total (10 for X, 5 for V) and passing the clue's own cells
through — their coverage lives here rather than in a file of its own, since
an X/V clue is just this layer's smallest arity with its total spelled in
the name.

Most of it is behaviour at the top seam — `verdict`: a clue's effect on the
completion, including the bare-repeat case the spec calls out by name. The
rule the layer emits is also read back directly, the one claim a solve cannot
make: that a clue emitted its *own* rule rather than being satisfied by
accident, and that no `add_all_different` rides along with it.

The rest read at the engine seam that a group-sum sums each cell's *value*
through `value_expr`, not its raw digit: with `doubler` in the stack it reads
a discovered modifier's `modifier_value`, and over a widened S-cell it reads
the `s_value` — proven the differential way, by forcing the channel and
checking the sum only balances through the folded value.
"""

from __future__ import annotations

from typing import cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from ortools.sat.python import cp_model

from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import all_different_groups, sum_rules
from gridfind.layers.group_sum import GroupSum
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _group_sum(cells: tuple[str, ...], total: int) -> Constraint:
    return Constraint(type="group-sum", params={"cells": list(cells), "sum": total})


def _clue(kind: str, cells: tuple[str, str]) -> Constraint:
    """An X or V alias clue — names its pair, leaves the sum to the alias."""
    return Constraint(type=kind, params={"cells": list(cells)})


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        ((_group_sum(("R1C1", "R1C2"), 5),), [(["R1C1", "R1C2"], 5)]),
        (
            (
                _group_sum(("R1C1", "R1C2"), 5),
                _group_sum(("R3C3", "R3C4", "R3C5"), 12),
            ),
            [(["R1C1", "R1C2"], 5), (["R3C3", "R3C4", "R3C5"], 12)],
        ),
        ((_clue("x", ("R1C1", "R1C2")),), [(["R1C1", "R1C2"], 10)]),
        ((_clue("v", ("R1C1", "R1C2")),), [(["R1C1", "R1C2"], 5)]),
    ],
    ids=["one clue", "two clues", "x alias", "v alias"],
)
def test_group_sum_emits_one_rule_per_clue(
    constraints: tuple[Constraint, ...],
    expected: list[tuple[list[str], int]],
) -> None:
    """One stateless layer, one rule per clue — including a clue that arrived
    as an alias, whose total the expansion fixed."""
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert sum_rules(engine) == expected


def test_group_sum_emits_no_all_different_rule() -> None:
    # The "total only" decision: a group-sum never adds distinctness pressure.
    puzzle = Puzzle(board=BOARD, constraints=(_group_sum(("R1C1", "R1C2"), 5),))
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert all_different_groups(engine) == []


def test_no_group_sum_constraint_emits_nothing() -> None:
    engine = build_engine([GridCells(), GroupSum()], board=BOARD)

    assert sum_rules(engine) == []


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


def test_a_v_clue_is_an_alias_for_a_group_sum_of_five() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_clue("v", ("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=3),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 2  # V binds the pair to 5


def test_an_x_clue_is_an_alias_for_a_group_sum_of_ten() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_clue("x", ("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=3),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 7  # X binds the pair to 10


@pytest.mark.parametrize("kind", ["x", "v"], ids=["x-alias", "v-alias"])
def test_an_alias_clue_that_also_states_its_own_sum_is_refused(kind: str) -> None:
    # The alias fixes the sum; a clue naming its own sum too is a
    # contradiction, refused before it ever reaches a solve.
    constraint = Constraint(type=kind, params={"cells": ["R1C1", "R1C2"], "sum": 99})
    puzzle = Puzzle(board=BOARD, constraints=(constraint,))

    with pytest.raises(MalformedPuzzleError, match=f"{kind!r}.*sum"):
        verdict(puzzle)


def test_a_group_sum_over_a_widened_cell_reads_its_s_value() -> None:
    # R1C1 is forced S with digits {2, 3}: its combined (concat) value is 23.
    # R1C2 is a singleton at 2. The sum reads each cell's value through
    # `value_expr`, so it balances at 23 + 2 = 25 — the S-cell's s_value, not
    # its raw digit (which would make 25 unreachable).
    engine = build_engine(
        [GridCells(), Schrodinger(), GroupSum()],
        (_group_sum(("R1C1", "R1C2"), 25),),
        board=Board(size=4, values=range(5)),
    )
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 2)
    engine.model.add(r1c1[1] == 3)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 2)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_a_plain_sudoku_with_no_group_sum_clue_is_unaffected() -> None:
    # A stack that never sees a group-sum clue adds no rule, and an ordinary
    # sudoku still resolves fully.
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


def test_group_sum_reads_the_doubled_value_when_a_cell_is_the_modifier() -> None:
    # 19 is unreachable by two plain 1-9 digits (max 18) but reachable once
    # one cell doubles (2*9 + 1). Forcing R1C1 to be the modifier isolates
    # the claim: the sum only balances if group-sum read R1C1's folded value,
    # not its raw digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _group_sum(("R1C1", "R1C2"), 19)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert 2 * solver.value(engine.d0("R1C1")) + solver.value(engine.d0("R1C2")) == 19


def test_a_sum_only_reachable_when_doubled_forces_discovery_in_the_group() -> None:
    # With nothing pinned: one-per-house puts exactly one modifier in row 1,
    # and 19 exceeds two plain 1-9 digits (max 18), so a free solve can satisfy
    # the clue only by discovering that modifier on R1C1 or R1C2. The clue
    # forces the discovery — the assertion reads the solver's choice, not a
    # fixture's.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _group_sum(("R1C1", "R1C2"), 19)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(is_modifier["R1C1"]) + solver.value(is_modifier["R1C2"]) == 1


def test_group_sum_falls_back_to_the_digit_when_the_cell_is_not_the_modifier() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _group_sum(("R1C1", "R1C2"), 19)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 0)
    engine.model.add(is_modifier["R1C2"] == 0)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
