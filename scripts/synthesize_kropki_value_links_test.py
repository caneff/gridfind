"""Guards for the synthesized labelled-non-default-kropki-value corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link's dot decodes with the labelled
value 3, never the default 1. The drift guard that the committed file
matches its synthesizer byte for byte lives in `corpus_drift_test.py`,
auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_kropki_value_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


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
