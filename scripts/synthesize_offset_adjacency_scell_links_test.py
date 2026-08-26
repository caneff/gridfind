"""Guards for the synthesized offset-adjacency-over-an-S-cell corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to one `anti-knight`
constraint and declares R1C1 an S-cell. The drift guard that the committed
file matches its synthesizer byte for byte lives in `corpus_drift_test.py`,
auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_offset_adjacency_scell_links as syn

from gridfind.puzzle import Constraint
from gridfind.s_directives import SCellPin
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_an_anti_knight_constraint_and_schrodinger(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    assert Constraint("anti-knight") in puzzle.constraints
    assert Constraint("schrodinger") in puzzle.constraints


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_pins_r1c1_as_an_s_cell_holding_1_and_2(name: str) -> None:
    _, state = link_to_puzzle(syn.CORPUS[name]())

    assert SCellPin(address="R1C1", pair=frozenset({1, 2})) in state.s_directives
