"""`_base`'s shared emit helpers, tested directly (issue #100).

`emit_distinct_count` is the deepest expansion in the package — one counting
rule costing O(cells x digits) solver constraints — and until the read side
existed it had no direct test at all: the only way to see it was a full solve
through `verdict`. These tests read the rule back instead.
"""

from collections.abc import Callable

from gridfind.engine import Engine, build_engine
from gridfind.layers import LAYER_REGISTRY
from gridfind.layers._base import emit_distinct_count
from gridfind.puzzle import Board


def _board_engine() -> Engine:
    """A 4x4 board and nothing else — cells to count over, no rules on them."""
    return build_engine([LAYER_REGISTRY["board"]], board=Board(size=4))


def test_emit_distinct_count_states_the_target_it_was_given(
    distinct_count_targets: Callable[[Engine], dict[str, int]],
) -> None:
    engine = _board_engine()
    cells = [engine.cells[address].content[0] for address in ("R1C1", "R1C2", "R1C3")]

    emit_distinct_count(engine, cells, target=2, label="trio")

    assert distinct_count_targets(engine) == {"trio": 2}


def test_emit_distinct_count_keeps_each_labelled_rule_separate(
    distinct_count_targets: Callable[[Engine], dict[str, int]],
) -> None:
    """Two counting rules on one engine stay two rules with their own targets —
    the label is what tells them apart."""
    engine = _board_engine()
    first = [engine.cells[address].content[0] for address in ("R1C1", "R1C2")]
    second = [engine.cells[address].content[0] for address in ("R2C1", "R2C2", "R2C3")]

    emit_distinct_count(engine, first, target=1, label="pair")
    emit_distinct_count(engine, second, target=3, label="trio")

    assert distinct_count_targets(engine) == {"pair": 1, "trio": 3}
