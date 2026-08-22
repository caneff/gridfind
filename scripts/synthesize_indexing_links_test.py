"""Guards for the synthesized 159-indexing corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to an `indexing`
constraint carrying the expected axis. The drift guard that the committed
file matches its synthesizer byte for byte lives in `corpus_drift_test.py`,
auto-discovered over every synthesizer.
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
