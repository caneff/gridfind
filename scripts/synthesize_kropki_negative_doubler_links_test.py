"""Guards for the synthesized kropki-negative-over-a-doubler-board corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes the marked dot, the
negated `diff != 7` rule over R4C4/R4C5, and the `doubler` constraint the
verdict turns on. The drift guard that the committed file matches its
synthesizer byte for byte lives in `corpus_drift_test.py`, auto-discovered
over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_kropki_negative_doubler_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_the_marked_dot_the_negated_rule_and_the_doubler(
    name: str,
) -> None:
    """Both fixtures carry the same marked positive clue, the same negated
    `diff != 7` constraint over R4C4/R4C5, and a `doubler` constraint — only
    the two links' givens differ, not their decoded ruleset."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert (
        Constraint("pair-difference", params={"cells": ["R1C1", "R1C2"], "diff": 1})
        in puzzle.constraints
    )
    assert (
        Constraint(
            "pair-difference",
            params={"cells": ["R4C4", "R4C5"], "diff": 7, "negate": True},
        )
        in puzzle.constraints
    )
    assert Constraint("doubler", params={}) in puzzle.constraints
