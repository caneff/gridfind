"""The `line-count-distinct` layer: its rule, and its dependency contract.

The rule — row *n* holds exactly *n* distinct digits — is read back here from
the rules the layer emits (issue #100). It is also proved end to end through
`verdict` in `verdict_test.py`, against a returned completion; the two are
different claims. This one says the layer states the right target for every
row, including rows a satisfiable witness would have satisfied by accident.
"""

from collections.abc import Callable

import pytest

from gridfind.engine import Engine, MissingDependencyError, build_engine
from gridfind.layers import LAYER_REGISTRY
from gridfind.puzzle import Board


def test_line_count_distinct_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([LAYER_REGISTRY["line-count-distinct"]])


@pytest.mark.parametrize("size", [4, 9], ids=["4x4", "9x9"])
def test_line_count_distinct_asks_row_n_for_n_distinct_digits(
    size: int,
    distinct_count_targets: Callable[[Engine], dict[str, int]],
) -> None:
    """somedoku's rule, stated per row, and sized off the board rather than a
    fixed 9x9."""
    engine = build_engine(
        [LAYER_REGISTRY["board"], LAYER_REGISTRY["line-count-distinct"]],
        board=Board(size=size),
    )

    targets = distinct_count_targets(engine)

    assert targets == {f"row{n}": n for n in range(1, size + 1)}
