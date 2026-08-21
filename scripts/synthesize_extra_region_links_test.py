"""Guards for the synthesized extra-region (windoku) corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): the committed file matches its
synthesizer byte for byte, and each link decodes to an `extra-region`
constraint carrying the expected window.
"""

from __future__ import annotations

import pytest
import synthesize_extra_region_links as syn

from gridfind.sudokumaker import link_to_puzzle

_EXPECTED_CELLS = ["R2C2", "R2C3", "R3C2", "R3C3"]


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_an_extra_region_constraint_over_the_window(
    name: str,
) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    groups = [
        constraint.params["cells"]
        for constraint in puzzle.constraints
        if constraint.type == "extra-region"
    ]
    assert groups == [_EXPECTED_CELLS]
