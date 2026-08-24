"""Guards for the synthesized clone corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to one `clone` constraint
over the cloned block R1C1/R3C3. The drift guard that the committed file
matches its synthesizer byte for byte lives in `corpus_drift_test.py`,
auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_clone_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle

# Every fixture clones the same non-attacking pair; only the givens / S-cell
# marks differ (see the synthesizer's found/broke docstrings).
_BLOCK = ["R1C1", "R3C3"]


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_a_clone_constraint_over_the_block(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    clones = [c for c in puzzle.constraints if c.type == "clone"]

    assert clones == [Constraint("clone", params={"cells": _BLOCK})]
