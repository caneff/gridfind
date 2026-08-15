"""cage behaviour, tested at two seams.

A cage names a set of cells and forbids repeats among them, adding no cover
pressure — unlike a region, it need not use every domain digit and never
forces a cell to become an S-cell. Structured like `group-sum`: one
stateless layer loops every `cage` constraint via `constraints_of` and emits
one no-repeats rule per clue.

Most of it is behaviour at the top seam — `verdict` — mirroring
`group_sum_test.py`: a clue's effect on the completion. The rules the layer
emits are also read back directly, and the cross-slot repeat a
Schrödinger-widened cage must catch is pinned directly the way
`schrodinger_test.py` does, since gridfind has no setter-facing S-cell pin
yet.

A killer cage's total is not this layer's concern — it is a `group-sum`
composed alongside a `cage`, tested at the two seams `group_sum_test.py`
covers and, for the composition itself, `verdict_test.py`.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import (
    Combine,
    Engine,
    MalformedPuzzleError,
    build_engine,
)
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.cage import Cage
from gridfind.layers.conftest import all_different_groups, distinct_count_targets
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _cage(
    cells: tuple[str, ...],
    name: str | None = None,
    distinct_over: str | None = None,
) -> Constraint:
    params: dict[str, object] = {"cells": list(cells)}
    if name is not None:
        params["name"] = name
    if distinct_over is not None:
        params["distinct-over"] = distinct_over
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


def test_values_distinct_cage_permits_a_value_distinct_from_its_digits() -> None:
    # R1C1 is forced S with digits {2, 3}: under the default `sum` combine its
    # value is 5. R1C2 is a singleton at 2. A digits-distinct cage would forbid
    # this (R1C1 holds digit 2 too); a values-distinct cage only cares that no
    # other cell's value equals 5, so the pair is feasible.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2"), distinct_over="value"),),
        board=Board(size=4, values=range(5)),
    )
    is_s = _is_s(engine)
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 2)
    engine.model.add(r1c1[1] == 3)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 2)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_values_distinct_cage_forbids_a_repeated_value() -> None:
    # Both R1C1 and R1C2 are forced S with the same pair {2, 3}: both sum to 5.
    # A values-distinct cage must reject the repeat even though no single slot
    # is a digit-for-digit clash.
    engine = build_engine(
        [GridCells(), Schrodinger(), Cage()],
        (_cage(("R1C1", "R1C2"), distinct_over="value"),),
        board=Board(size=4, values=range(5)),
    )
    is_s = _is_s(engine)
    r1c1 = engine.contents("R1C1")
    r1c2 = engine.contents("R1C2")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 2)
    engine.model.add(r1c1[1] == 3)
    engine.model.add(is_s["R1C2"] == 1)
    engine.model.add(r1c2[0] == 2)
    engine.model.add(r1c2[1] == 3)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_values_distinct_cage_collides_a_doubled_value_with_an_s_value() -> None:
    # The no-offset decision (ADR-0009 decision 3): a value is a number, so a
    # cell worth 18 through the modifier_value channel (a doubler's 2·9) and one
    # worth 18 through the s_value channel (an S-cell whose two digits combine to
    # 18) are the same value and clash — even though the two came from different
    # channels.
    engine = build_engine(
        [], constraints=(_cage(("R1C1", "R1C2"), distinct_over="value"),), board=BOARD
    )
    engine.add_cell("R1C1", low=1, high=9)
    engine.add_cell("R1C2", low=1, high=9)
    modifier_value = engine.model.new_int_var(0, 18, "R1C1.modifier_value")
    s_value = engine.model.new_int_var(0, 99, "R1C2.s_value")
    engine.register_structure("modifier_value", {"R1C1": modifier_value})
    engine.register_structure("s_value", {"R1C2": s_value})
    engine.model.add(modifier_value == 18)
    engine.model.add(s_value == 18)
    cage = Cage()
    cage.register(engine)
    cage.emit(engine)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_values_distinct_cage_reads_a_modifier_value_not_the_raw_digit() -> None:
    # A cell in the modifier_value channel (a discovered doubler's 2·d0)
    # contributes that value, not its digit. R1C1's raw digit is 3 but its
    # modifier_value is 6; pinning R1C2's digit to 6 clashes only if the cage
    # read the value, so INFEASIBLE proves it reads modifier_value.
    engine = build_engine(
        [], constraints=(_cage(("R1C1", "R1C2"), distinct_over="value"),), board=BOARD
    )
    engine.add_cell("R1C1", low=1, high=9)
    engine.add_cell("R1C2", low=1, high=9)
    modifier_value = engine.model.new_int_var(0, 18, "R1C1.modifier_value")
    engine.register_structure("modifier_value", {"R1C1": modifier_value})
    engine.model.add(modifier_value == 6)
    engine.model.add(engine.d0("R1C1") == 3)
    engine.model.add(engine.d0("R1C2") == 6)
    cage = Cage()
    cage.register(engine)
    cage.emit(engine)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_values_distinct_cage_collides_a_doubled_s_cell_at_twice_its_s_value() -> None:
    # A cell in both channels is a doubled S-cell, worth 2·s_value (ADR-0010):
    # value_expr folds modifier_value over s_value, so the cage reads 6 (=2·3),
    # not the bare s_value 3. A plain cell valued 6 clashes with it — the cage
    # reads the folded value.
    engine = build_engine(
        [], constraints=(_cage(("R1C1", "R1C2"), distinct_over="value"),), board=BOARD
    )
    engine.add_cell("R1C1", low=1, high=9)
    engine.add_cell("R1C2", low=1, high=9)
    s_value = engine.model.new_int_var(0, 18, "R1C1.s_value")
    modifier_value = engine.model.new_int_var(0, 36, "R1C1.modifier_value")
    engine.model.add(s_value == 3)
    engine.model.add(modifier_value == 2 * s_value)
    engine.register_structure("s_value", {"R1C1": s_value})
    engine.register_structure("modifier_value", {"R1C1": modifier_value})
    engine.model.add(engine.d0("R1C2") == 6)
    cage = Cage()
    cage.register(engine)
    cage.emit(engine)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


@pytest.mark.parametrize(
    ("combine", "infeasible"),
    [
        pytest.param("sum", True, id="sum-makes-2-3-equal-5"),
        pytest.param("concat", False, id="concat-makes-2-3-equal-23"),
    ],
)
def test_schrodinger_combine_rule_sets_the_s_cell_value(
    combine: Combine, *, infeasible: bool
) -> None:
    # The schrodinger layer's `combine` rule decides how an S-cell's two digits
    # read as one value — the value it reifies into the s_value channel: {2, 3}
    # is 5 under `sum`, 23 under `concat`. Beside a singleton 5, a values-distinct
    # cage clashes only when the S-cell also reads 5.
    engine = build_engine(
        [GridCells(), Schrodinger(combine=combine), Cage()],
        (_cage(("R1C1", "R1C2"), distinct_over="value"),),
        board=Board(size=4, values=range(6)),
    )
    is_s = _is_s(engine)
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 2)
    engine.model.add(r1c1[1] == 3)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 5)

    status = cp_model.CpSolver().solve(engine.model)

    if infeasible:
        assert status == cp_model.INFEASIBLE
    else:
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_a_values_distinct_cage_resolves_found_through_verdict() -> None:
    # End-to-end at the verdict seam: a values-distinct cage of two singletons
    # holding distinct digits (hence distinct values) is found.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2"), distinct_over="value"),),
        givens=(Given(address="R1C1", digit=2), Given(address="R1C2", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


@pytest.mark.parametrize("distinct_over", [None, "digit"], ids=["unstated", "explicit"])
def test_digits_distinct_is_the_default(distinct_over: str | None) -> None:
    # An unstated distinct-over and an explicit "digit" resolve the same
    # verdict — a forced digit repeat breaks either way.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_cage(("R1C1", "R1C2"), distinct_over=distinct_over),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"


def test_digits_distinct_cage_reads_the_raw_digit_not_the_value_channel() -> None:
    # digits-distinct forbids a repeated digit — the placed symbol — not a
    # value (ADR-0009 decision 1). R1C1's modifier_value is 6 while its digit is
    # 3; R1C2's digit is 6. The values collide (6, 6) but the digits differ, so
    # a digits-distinct cage stays FEASIBLE — proof it reads raw content, not
    # the value channel a values-distinct cage would.
    engine = build_engine([], constraints=(_cage(("R1C1", "R1C2")),), board=BOARD)
    engine.add_cell("R1C1", low=1, high=9)
    engine.add_cell("R1C2", low=1, high=9)
    modifier_value = engine.model.new_int_var(0, 18, "R1C1.modifier_value")
    engine.register_structure("modifier_value", {"R1C1": modifier_value})
    engine.model.add(modifier_value == 6)
    engine.model.add(engine.d0("R1C1") == 3)
    engine.model.add(engine.d0("R1C2") == 6)
    cage = Cage()
    cage.register(engine)
    cage.emit(engine)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_cage_rejects_an_unknown_distinct_over() -> None:
    puzzle = Puzzle(
        board=BOARD, constraints=(_cage(("R1C1", "R1C2"), distinct_over="bogus"),)
    )

    with pytest.raises(MalformedPuzzleError, match="bogus"):
        verdict(puzzle)
