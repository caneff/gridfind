"""Guards for the synthesized labelled-non-default-kropki-value corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive
lives in the on-demand `links_test` e2e suite): the committed file matches
its synthesizer byte for byte, and each link's dot decodes with the labelled
value 3, never the default 1.
"""

from __future__ import annotations

import pytest
import synthesize_kropki_value_links as syn

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
def test_link_decodes_the_labelled_value_not_the_default(name: str) -> None:
    """Each fixture's dot decodes to `pair-difference` with `diff` 3 (the
    labelled value): a decoder that coerced an unlabelled-looking dot to the
    default difference 1 would fail this even though both fixtures still
    parse."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert (
        Constraint("pair-difference", params={"cells": ["R1C1", "R1C2"], "diff": 3})
        in puzzle.constraints
    )
