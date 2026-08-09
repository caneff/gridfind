"""`_base`'s shared emit helpers, tested directly (issue #100).

`emit_distinct_count` is the deepest expansion in the package — one counting
rule costing O(cells x digits) solver constraints — and until the read side
existed it had no direct test at all: the only way to see it was a full solve
through `verdict`. These tests read the rule back instead.
"""

from ortools.sat.python import cp_model

from gridfind.engine import Engine, build_engine
from gridfind.layers._base import emit_distinct_count, emit_over_pairs
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import distinct_count_targets, pair_sum_rules
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
    up is the difference: a counting rule sums per-digit markers, a pair-sum
    sums cell content. Neither read side may pick up the other's rule.
    """
    engine = _board_engine()
    pair = [engine.cells[address].content[0] for address in ("R1C1", "R1C2")]

    engine.model.add(sum(pair) == 5)
    emit_distinct_count(engine, pair, target=2, label="pair")

    assert pair_sum_rules(engine) == [(["R1C1", "R1C2"], 5)]
    assert distinct_count_targets(engine) == {"pair": 2}


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

    assert pair_sum_rules(engine) == [
        (["R1C1", "R1C2"], 5),
        (["R2C1", "R2C2"], 5),
    ]


def test_emit_over_pairs_does_nothing_for_no_pairs() -> None:
    engine = _board_engine()

    emit_over_pairs(engine, [], _sums_to_five)

    assert pair_sum_rules(engine) == []
