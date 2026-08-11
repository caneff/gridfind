"""`_base`'s shared emit helpers, tested directly.

`emit_distinct_count` is the deepest expansion in the package — one counting
rule costing O(cells x digits) solver constraints — and until the read side
existed it had no direct test at all: the only way to see it was a full solve
through `verdict`. These tests read the rule back instead.
"""

from ortools.sat.python import cp_model

from gridfind.engine import Engine, build_engine
from gridfind.layers._base import emit_distinct_count, emit_house, emit_over_pairs
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import (
    distinct_count_targets,
    pair_difference_rules,
    sum_rules,
)
from gridfind.puzzle import Board


def _board_engine() -> Engine:
    """A 4x4 board and nothing else — cells to count over, no rules on them."""
    return build_engine([GridCells()], board=Board(size=4))


def test_emit_distinct_count_states_the_target_it_was_given() -> None:
    engine = _board_engine()
    cells = [engine.cells[address].content[0] for address in ("R1C1", "R1C2", "R1C3")]

    emit_distinct_count(engine, cells, target=2, label="trio")

    assert distinct_count_targets(engine) == {"trio": 2}


def test_emit_distinct_count_keeps_each_labelled_rule_separate() -> None:
    """Two counting rules on one engine stay two rules with their own targets —
    the label is what tells them apart."""
    engine = _board_engine()
    first = [engine.cells[address].content[0] for address in ("R1C1", "R1C2")]
    second = [engine.cells[address].content[0] for address in ("R2C1", "R2C2", "R2C3")]

    emit_distinct_count(engine, first, target=1, label="pair")
    emit_distinct_count(engine, second, target=3, label="trio")

    assert distinct_count_targets(engine) == {"pair": 1, "trio": 3}


def test_a_counting_rule_and_a_sum_over_cells_are_told_apart() -> None:
    """Both rules state themselves as a sum fixed to one value. What they add
    up is the difference: a counting rule sums per-digit markers, a bare sum
    rule sums cell content. Neither read side may pick up the other's rule.
    """
    engine = _board_engine()
    pair = [engine.cells[address].content[0] for address in ("R1C1", "R1C2")]

    engine.model.add(sum(pair) == 5)
    emit_distinct_count(engine, pair, target=2, label="pair")

    assert sum_rules(engine) == [(["R1C1", "R1C2"], 5)]
    assert distinct_count_targets(engine) == {"pair": 2}


def _differs_by_three(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
    d = engine.model.new_int_var(0, 3, f"{a.name}-{b.name}.diff")
    engine.model.add_abs_equality(d, a - b)
    engine.model.add(d == 3)


def test_a_counting_rule_and_a_pair_difference_are_told_apart() -> None:
    """A counting rule's `present` sum and a difference rule's `d == k` pin
    are both a single-var linear equality over a non-content var —
    structurally identical shapes read by two different functions. Neither
    read side may pick up the other's rule."""
    engine = _board_engine()
    pair = (engine.cells["R1C1"].content[0], engine.cells["R1C2"].content[0])
    trio = [engine.cells[address].content[0] for address in ("R2C1", "R2C2", "R2C3")]

    emit_over_pairs(engine, [pair], _differs_by_three)
    emit_distinct_count(engine, trio, target=2, label="trio")

    assert pair_difference_rules(engine) == [(["R1C1", "R1C2"], 3)]
    assert distinct_count_targets(engine) == {"trio": 2}


def _sums_to_five(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
    engine.model.add(a + b == 5)


def test_emit_over_pairs_applies_rel_to_each_pair() -> None:
    """`rel` runs once per pair, each pair independent of the others — proof
    via a `rel` that states a sum, read back through the same seam a direct
    `model.add(sum(pair) == total)` call would produce."""
    engine = _board_engine()
    first = (engine.cells["R1C1"].content[0], engine.cells["R1C2"].content[0])
    second = (engine.cells["R2C1"].content[0], engine.cells["R2C2"].content[0])

    emit_over_pairs(engine, [first, second], _sums_to_five)

    assert sum_rules(engine) == [
        (["R1C1", "R1C2"], 5),
        (["R2C1", "R2C2"], 5),
    ]


def test_emit_over_pairs_does_nothing_for_no_pairs() -> None:
    engine = _board_engine()

    emit_over_pairs(engine, [], _sums_to_five)

    assert sum_rules(engine) == []


def test_emit_house_forces_the_extra_digit_into_the_width_two_cells_second_slot() -> (
    None
):
    """Three cells — two width-1, one width-2 — over a 4-digit board: the
    fourth digit has nowhere to live but the width-2 cell's second slot, and
    no-repeats + cover (schrodinger's is_S-gated counting) is one
    rule, not stated as a count."""
    engine = _board_engine()
    a = engine.model.new_int_var(1, 4, "a")
    b = engine.model.new_int_var(1, 4, "b")
    c0 = engine.model.new_int_var(1, 4, "c0")
    c1 = engine.model.new_int_var(1, 4, "c1")

    emit_house(engine, [[a], [b], [c0, c1]], label="house")

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assigned = [solver.value(v) for v in (a, b, c0, c1)]
    assert sorted(assigned) == [1, 2, 3, 4]


def test_emit_house_is_infeasible_when_the_slots_cant_cover_the_domain() -> None:
    """Two width-1 cells alone can't cover a 4-digit domain — cover, not just
    no-repeats, is part of the one rule."""
    engine = _board_engine()
    a = engine.model.new_int_var(1, 4, "a")
    b = engine.model.new_int_var(1, 4, "b")

    emit_house(engine, [[a], [b]], label="house")

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
