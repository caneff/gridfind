"""Guards for the synthesized quadruple (`type 303`) corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to one `quadruple`
constraint carrying the expected 2x2 block and required digits. The drift
guard that the committed file matches its synthesizer byte for byte lives in
`corpus_drift_test.py`, auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_quadruple_links as syn

from gridfind.sudokumaker import link_to_puzzle

# Both fixtures clue the straddling block R2C2/R2C3/R3C2/R3C3; only the
# required digits differ (see the synthesizer's found/broke docstrings).
_BLOCK = ["R2C2", "R2C3", "R3C2", "R3C3"]
_EXPECTED_DIGITS = {
    "found-quadruple-4x4": [1],
    "broke-quadruple-4x4": [4],
}


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_a_quadruple_constraint_over_the_block(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    clues = [
        constraint.params
        for constraint in puzzle.constraints
        if constraint.type == "quadruple"
    ]

    assert clues == [{"cells": _BLOCK, "digits": _EXPECTED_DIGITS[name]}]
