"""Guards for the synthesized double-arrow (`type 409`) corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to one `line` constraint
carrying the expected path. The drift guard that the committed file matches
its synthesizer byte for byte lives in `corpus_drift_test.py`, auto-discovered
over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_double_arrow_links as syn

from gridfind.sudokumaker import link_to_puzzle

_PATH = ["R1C1", "R2C2", "R3C3"]


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_a_double_arrow_line_constraint(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    lines = [
        constraint.params
        for constraint in puzzle.constraints
        if constraint.type == "line"
    ]

    assert lines == [{"relation": "double-arrow", "path": _PATH}]
