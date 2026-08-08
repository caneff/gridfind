"""The `line-count-distinct` layer's own dependency contract.

The rule itself — row *n* holds exactly *n* distinct digits — is tested through
`verdict` in `verdict_test.py`, not against the CP-SAT model shape here.
`test_line_count_distinct_found_when_row_counts_are_satisfiable` asserts row 1
holds exactly one distinct digit, which an AllDifferent could never satisfy.
"""

import pytest

from gridfind.engine import MissingDependencyError, build_engine
from gridfind.layers import LAYER_REGISTRY


def test_line_count_distinct_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([LAYER_REGISTRY["line-count-distinct"]])
