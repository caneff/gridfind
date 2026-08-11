"""cage behaviour, tested at two seams.

A cage names a set of cells and forbids repeats among them, adding no cover
pressure — unlike a region, it need not use every domain digit and never
forces a cell to become an S-cell. Structured like `pair-sum`: one
stateless layer loops every `cage` constraint via `constraints_of` and emits
one no-repeats rule per clue.

Most of it is behaviour at the top seam — `verdict` — mirroring
`pair_sum_test.py`: a clue's effect on the completion. The rules the layer
emits are also read back directly, and the cross-slot repeat a
Schrödinger-widened cage must catch is pinned directly the way
`schrodinger_test.py` does, since gridfind has no setter-facing S-cell pin
yet.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import Engine, build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.cage import Cage
from gridfind.layers.conftest import (
    all_different_groups,
    distinct_count_targets,
    pair_sum_rules,
)
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _cage(
    cells: tuple[str, ...], name: str | None = None, value: int | None = None
) -> Constraint:
    params: dict[str, object] = {"cells": list(cells)}
    if name is not None:
        params["name"] = name
    if value is not None:
        params["value"] = value
    return Constraint(type="cage", params=params)


def _is_s(engine: Engine) -> dict[str, cp_model.IntVar]:
    return cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        ((_cage(("R1C1", "R1C2", "R1C3")),), [["R1C1", "R1C2", "R1C3"]]),
        (
            (_cage(("R1C1", "R1C2")), _cage(("R3C3", "R3C4", "R3C5"))),
            [["R1C1", "R1C2"], ["R3C3", "R3C4", "R3C5"]],
        ),
        ((_cage(("R1C1", "R1C2"), name="killer-a"),), [["R1C1", "R1C2"]]),
    ],
    ids=["one clue", "two clues", "named clue"],
)
def test_cage_emits_one_all_different_rule_per_clue(
    constraints: tuple[Constraint, ...],
    expected: list[list[str]],
) -> None:
    """One stateless layer, one rule per clue — including a clue that carries
    a `name`, reserved and unread today."""
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert all_different_groups(engine) == expected


def test_no_cage_constraint_emits_nothing() -> None:
    # A stack that never sees a `cage` clue adds no rule.
    engine = build_engine([GridCells(), Cage()], board=BOARD)

    assert all_different_groups(engine) == []


def test_cage_adds_no_cover_pressure_at_the_emit_seam() -> None:
    # No counting rule at all — a cage never states a target digit count,
    # unlike the is_S-gated cover rule a region emits.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2")),),
        board=Board(size=4, values=range(5)),
    )

    assert distinct_count_targets(engine) == {}


def test_cage_rule_reaches_both_slots_of_a_widened_cell() -> None:
    # On a Schrödinger-widened board the no-repeats rule runs over each
    # cage cell's whole content sequence, not just its d0 — this cage's
    # two cells contribute two slots each.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2")),),
        board=Board(size=4, values=range(5)),
    )

    assert all_different_groups(engine) == [["R1C1", "R1C1", "R1C2", "R1C2"]]


def test_a_cage_permits_a_completion_leaving_its_cells_singleton() -> None:
    # The cage forces no S-cell: pinning every cage cell to not-S is still
    # feasible, so the cage itself adds no pressure toward S-cell-ness.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2", "R1C3", "R1C4")),),
        board=Board(size=4, values=range(5)),
    )
    is_s = _is_s(engine)
    for address in ("R1C1", "R1C2", "R1C3", "R1C4"):
        engine.model.add(is_s[address] == 0)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_cage_forbids_a_repeat_across_an_s_cells_two_digits() -> None:
    # R1C1 is forced S with digits {0, 1}; R1C2's singleton digit repeats
    # R1C1's second digit — a cross-slot repeat the rule must still catch.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2")),),
        board=Board(size=2, values=range(3)),
    )
    is_s = _is_s(engine)
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 0)
    engine.model.add(r1c1[1] == 1)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 1)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_cage_permits_an_s_cell_beside_a_non_conflicting_singleton() -> None:
    # The satisfiable companion to the above — same S-cell pinning, a
    # singleton digit that does not collide with either of its two digits.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2")),),
        board=Board(size=2, values=range(3)),
    )
    is_s = _is_s(engine)
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 0)
    engine.model.add(r1c1[1] == 1)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 2)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_a_satisfiable_cage_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == (1,)
    assert result.witness["R1C2"] == (2,)
    assert result.witness["R1C3"][0] not in (1, 2)


def test_a_cage_forced_to_repeat_resolves_broke() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_cages_each_constrain_their_own_cells_independently() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2")), _cage(("R3C3", "R3C4"))),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=6)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"][0] != 1
    assert result.witness["R3C4"][0] != 6


def test_a_broken_second_cage_breaks_the_whole_puzzle() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2")), _cage(("R3C3", "R3C4"))),
        givens=(Given(address="R3C3", digit=1), Given(address="R3C4", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_cage_holding_a_proper_subset_of_the_domain_is_found() -> None:
    # A 7-cell cage on a 9-digit board — no need to use every domain digit.
    cells = tuple(f"R1C{c}" for c in range(1, 8))
    puzzle = Puzzle(board=BOARD, constraints=(_cage(cells),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    digits = [result.witness[address][0] for address in cells]
    assert len(set(digits)) == len(digits)


# --- killer sum ------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, [(["R1C1", "R1C2"], 5)]), (0, []), (None, [])],
    ids=[
        "positive value emits a sum rule",
        "zero is region-only",
        "absent is region-only",
    ],
)
def test_a_cage_sum_rule_is_emitted_only_for_a_positive_value(
    value: int | None, expected: list[tuple[list[str], int]]
) -> None:
    puzzle = Puzzle(board=BOARD, constraints=(_cage(("R1C1", "R1C2"), value=value),))
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert pair_sum_rules(engine) == expected


def test_a_cage_sum_still_emits_its_no_repeats_rule() -> None:
    # The sum is additional, not a replacement — the cage's cells must still
    # be pairwise distinct.
    puzzle = Puzzle(board=BOARD, constraints=(_cage(("R1C1", "R1C2"), value=5),))
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert all_different_groups(engine) == [["R1C1", "R1C2"]]


def test_a_cage_sum_forces_the_witness_to_match_it() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2"), value=3),),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C2"] == (2,)


def test_a_cage_sum_that_cannot_be_met_resolves_broke() -> None:
    # 1 + 5 already sums to 6, wanting 3 — no completion can satisfy it.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2"), value=3),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=5)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_cage_sum_over_an_s_cell_adds_both_of_its_digits() -> None:
    # R1C1 is forced S with digits {0, 1}; R1C2 is a singleton at 2. The sum
    # only balances (0 + 1 + 2 == 3) if the S-cell contributes both digits.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2"), value=3),),
        board=Board(size=4, values=range(5)),
    )
    is_s = _is_s(engine)
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 0)
    engine.model.add(r1c1[1] == 1)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 2)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_a_cage_sum_over_an_s_cell_rejects_a_total_matching_only_one_digit() -> None:
    # Same S-cell pinning as above, but a target that only balances if the
    # S-cell contributed one digit, not both (0 + 2 == 2, not 3).
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2"), value=2),),
        board=Board(size=4, values=range(5)),
    )
    is_s = _is_s(engine)
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 0)
    engine.model.add(r1c1[1] == 1)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 2)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_a_cage_sum_over_a_non_s_cell_is_unchanged_on_a_schrodinger_board() -> None:
    # The companion regression: pinning both cells not-S, the sum still reads
    # each cell's single real digit — the plain-cell path is untouched by
    # the S-cell awareness above.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2"), value=3),),
        board=Board(size=4, values=range(5)),
    )
    is_s = _is_s(engine)
    engine.model.add(is_s["R1C1"] == 0)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C1") == 1)
    engine.model.add(engine.d0("R1C2") == 2)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
