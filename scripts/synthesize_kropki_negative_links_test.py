"""Guards for the synthesized white-kropki-negative corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive
lives in the on-demand `links_test` e2e suite): the committed file matches
its synthesizer byte for byte, and each link decodes the marked dot plus the
negated `diff != 2` rule over R3C3/R3C4, the pair the verdict turns on.
"""

from __future__ import annotations

import pytest
import synthesize_kropki_negative_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_the_marked_dot_and_the_negated_rule(name: str) -> None:
    """Both fixtures carry the same marked positive clue and the same negated
    `diff != 2` constraint over R3C3/R3C4 — only the two links' givens differ,
    not their decoded ruleset."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert (
        Constraint("pair-difference", params={"cells": ["R1C1", "R1C2"], "diff": 1})
        in puzzle.constraints
    )
    assert (
        Constraint(
            "pair-difference",
            params={"cells": ["R3C3", "R3C4"], "diff": 2, "negate": True},
        )
        in puzzle.constraints
    )
