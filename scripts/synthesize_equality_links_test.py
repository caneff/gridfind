"""Guards for the synthesized equality-cage corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes its named cage to
`cage` + `equality-cage` over the expected cells. The drift guard that the
committed file matches its synthesizer byte for byte lives in
`corpus_drift_test.py`, auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_equality_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize(
    ("name", "cells"),
    [
        ("found-equality-9x9", ["R1C1", "R1C4", "R1C6", "R1C7"]),
        ("broke-equality-parity-9x9", ["R1C2", "R1C4", "R1C6", "R1C7"]),
        ("broke-equality-rank-9x9", ["R1C1", "R1C2", "R1C3", "R1C4"]),
        ("broke-equality-middle-9x9", ["R1C2", "R1C4", "R1C5", "R1C7"]),
    ],
)
def test_link_decodes_to_cage_plus_equality_cage(name: str, cells: list[str]) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert Constraint("cage", params={"cells": cells}) in puzzle.constraints
    assert Constraint("equality-cage", params={"cells": cells}) in puzzle.constraints
