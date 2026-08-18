"""Guards for the synthesized 159-indexing corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive
lives in the on-demand `links_test` e2e suite): the committed file matches
its synthesizer byte for byte, and each link decodes to an `indexing`
constraint carrying the expected axis.
"""

from __future__ import annotations

import pytest
import synthesize_indexing_links as syn

from gridfind.sudokumaker import link_to_puzzle

_EXPECTED_AXIS: dict[str, str] = {
    "found-indexing-row-4x4": "row",
    "broke-indexing-row-4x4": "row",
    "found-indexing-col-4x4": "col",
    "broke-indexing-col-4x4": "col",
    "found-indexing-scell-col-4x4": "col",
    "broke-indexing-scell-col-4x4": "col",
}


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_an_indexing_constraint_on_the_expected_axis(
    name: str,
) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    axes = {
        constraint.params["axis"]
        for constraint in puzzle.constraints
        if constraint.type == "indexing"
    }
    assert axes == {_EXPECTED_AXIS[name]}
