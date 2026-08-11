"""pair-sum behaviour, tested at two seams.

Most of it is behaviour at the top seam — `verdict`: a clue's
effect on the completion, and the XV aliases riding on top, where a `v` clue is
a pair-sum of 5 and an `x` clue a pair-sum of 10.

The rules the layer emits are read back directly, which is the one
claim a solve cannot make: that a clue emitted its *own* rule rather than being
satisfied by accident.

Two more tests read at the engine seam: with `doubler`
in the stack, a pair-sum reads a named cell's `"modifier_value"` instead of its
raw digit — proven the same differential way as the two seams above, by
forcing `is_modifier` and checking the sum only balances through the fold.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.conftest import pair_sum_rules
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _pair_sum(cells: tuple[str, str], total: int) -> Constraint:
    return Constraint(type="pair-sum", params={"cells": list(cells), "sum": total})


def _clue(kind: str, cells: tuple[str, str]) -> Constraint:
    """An X or V alias clue — names its pair, leaves the sum to the alias."""
    return Constraint(type=kind, params={"cells": list(cells)})


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        ((_pair_sum(("R1C1", "R1C2"), 5),), [(["R1C1", "R1C2"], 5)]),
        (
            (_pair_sum(("R1C1", "R1C2"), 5), _pair_sum(("R3C3", "R3C4"), 10)),
            [(["R1C1", "R1C2"], 5), (["R3C3", "R3C4"], 10)],
        ),
        ((_clue("x", ("R1C1", "R1C2")),), [(["R1C1", "R1C2"], 10)]),
        ((_clue("v", ("R1C1", "R1C2")),), [(["R1C1", "R1C2"], 5)]),
    ],
    ids=["one clue", "two clues", "x alias", "v alias"],
)
def test_pair_sum_emits_one_rule_per_clue(
    constraints: tuple[Constraint, ...],
    expected: list[tuple[list[str], int]],
) -> None:
    """One stateless layer, one rule per clue — including a clue that arrived
    as an alias, whose total the expansion fixed."""
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert pair_sum_rules(engine) == expected


def test_a_satisfiable_pair_resolves_found() -> None:
    puzzle = Puzzle(board=BOARD, constraints=(_pair_sum(("R1C1", "R1C2"), 5),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"][0] + result.witness["R1C2"][0] == 5


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
    assert result.witness["R1C2"][0] == 4  # 1 + 4 == 5
    assert result.witness["R3C4"][0] == 4  # 6 + 4 == 10


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


def test_a_v_clue_is_an_alias_for_a_pair_sum_of_five() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_clue("v", ("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=3),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] == 2  # V binds the pair to 5


def test_an_x_clue_is_an_alias_for_a_pair_sum_of_ten() -> None:
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


def test_pair_sum_reads_the_doubled_value_when_a_cell_is_the_modifier() -> None:
    # 19 is unreachable by two plain 1-9 digits (max 18) but reachable once
    # one cell doubles (2*9 + 1). Forcing R1C1 to be the modifier isolates
    # the claim: the sum only balances if pair-sum read R1C1's folded value,
    # not its raw digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _pair_sum(("R1C1", "R1C2"), 19)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert 2 * solver.value(engine.d0("R1C1")) + solver.value(engine.d0("R1C2")) == 19


def test_a_sum_only_reachable_when_doubled_forces_discovery_in_the_pair() -> None:
    # With nothing pinned: one-per-house puts exactly one modifier in row 1,
    # and 19 exceeds two plain 1-9 digits (max 18), so a free solve can satisfy
    # the clue only by discovering that modifier on R1C1 or R1C2. The clue forces
    # the discovery — the assertion reads the solver's choice, not a fixture's.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _pair_sum(("R1C1", "R1C2"), 19)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(is_modifier["R1C1"]) + solver.value(is_modifier["R1C2"]) == 1


def test_pair_sum_falls_back_to_the_digit_when_the_cell_is_not_the_modifier() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _pair_sum(("R1C1", "R1C2"), 19)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 0)
    engine.model.add(is_modifier["R1C2"] == 0)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
