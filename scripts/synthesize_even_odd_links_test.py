"""Guards for the synthesized even/odd corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to a `parity`
constraint carrying the expected parity and cell. The drift guard that the
committed file matches its synthesizer byte for byte lives in
`corpus_drift_test.py`, auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_even_odd_links as syn

from gridfind.sudokumaker import link_to_puzzle

_EXPECTED_PARITY = {
    "found-even-4x4": "even",
    "broke-even-4x4": "even",
    "found-odd-4x4": "odd",
    "broke-odd-4x4": "odd",
    "broke-odd-doubler-4x4": "odd",
}


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_a_parity_constraint_over_r1c1(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    clues = [
        constraint.params
        for constraint in puzzle.constraints
        if constraint.type == "parity"
    ]

    assert clues == [{"parity": _EXPECTED_PARITY[name], "cells": ["R1C1"]}]


def test_broke_odd_doubler_link_also_decodes_a_doubler_constraint() -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS["broke-odd-doubler-4x4"]())

    assert any(constraint.type == "doubler" for constraint in puzzle.constraints)
