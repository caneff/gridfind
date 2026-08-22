"""Guards for the synthesized xv-negative corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes the negated `sum != 5`
rule over every orthogonally-adjacent pair, including R3C3/R3C4 — the pair
the verdict turns on. The drift guard that the committed file matches its
synthesizer byte for byte lives in `corpus_drift_test.py`, auto-discovered
over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_xv_negative_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_the_negated_rule_over_the_deciding_pair(name: str) -> None:
    """Both fixtures carry no positive XV clue and the same negated `sum !=
    5` constraint over R3C3/R3C4 — only the two links' givens differ, not
    their decoded ruleset."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert not any(c.type in ("x", "v") for c in puzzle.constraints)
    assert (
        Constraint(
            "group-sum",
            params={"cells": ["R3C3", "R3C4"], "sum": 5, "negate": True},
        )
        in puzzle.constraints
    )
