"""Guards for the synthesized nonconsecutive (`type 15`) corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to the `nonconsecutive`
constraint. The drift guard that the committed file matches its synthesizer
byte for byte lives in `corpus_drift_test.py`, auto-discovered over every
synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_nonconsecutive_links as syn

from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_a_nonconsecutive_constraint(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    constraint_types = {constraint.type for constraint in puzzle.constraints}

    assert "nonconsecutive" in constraint_types
