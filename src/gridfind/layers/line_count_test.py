"""The `line-count-distinct` layer's own dependency contract.

The rule itself — row *n* holds exactly *n* distinct digits — is tested through
`verdict` in `verdict_test.py`, against the returned completion rather than
against the CP-SAT model shape here. A satisfiable 9x9 puts exactly one distinct
digit in row 1, which an AllDifferent could never satisfy.
"""

import pytest

from gridfind.engine import MissingDependencyError, build_engine
from gridfind.layers import LAYER_REGISTRY


def test_line_count_distinct_requires_board() -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([LAYER_REGISTRY["line-count-distinct"]])
