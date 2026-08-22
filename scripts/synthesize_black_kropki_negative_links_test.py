"""Guards for the synthesized black-kropki-negative corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes the marked dot plus the
negated `k != 3` rule over R3C3/R3C4, the pair the verdict turns on. The
drift guard that the committed file matches its synthesizer byte for byte
lives in `corpus_drift_test.py`, auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_black_kropki_negative_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_the_marked_dot_and_the_negated_rule(name: str) -> None:
    """Both fixtures carry the same marked positive clue and the same negated
    `k != 3` constraint over R3C3/R3C4 — only the two links' givens differ,
    not their decoded ruleset."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert (
        Constraint("pair-ratio", params={"cells": ["R1C1", "R1C2"], "k": 2})
        in puzzle.constraints
    )
    assert (
        Constraint(
            "pair-ratio",
            params={"cells": ["R3C3", "R3C4"], "k": 3, "negate": True},
        )
        in puzzle.constraints
    )
