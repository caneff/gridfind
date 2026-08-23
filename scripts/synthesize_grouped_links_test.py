"""Guards for the synthesized grouped-line (`type 406`) corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to one `line` constraint
carrying the expected path and groups. The drift guard that the committed
file matches its synthesizer byte for byte lives in `corpus_drift_test.py`,
auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_grouped_links as syn

from gridfind.sudokumaker import link_to_puzzle

# Each corpus name's expected (path, groups) — entropic names carry the
# 9x9 fixture's 3-cell path and bands, parity names the 4x4 fixture's 2-cell
# path and parities.
_EXPECTED: dict[str, tuple[list[str], list[int]]] = {
    "found-grouped-entropic-9x9": (["R1C1", "R2C2", "R3C3"], syn._ENTROPIC_GROUPS),
    "broke-grouped-entropic-9x9": (["R1C1", "R2C2", "R3C3"], syn._ENTROPIC_GROUPS),
    "found-grouped-parity-4x4": (["R1C1", "R1C2"], syn._PARITY_GROUPS),
    "broke-grouped-parity-4x4": (["R1C1", "R1C2"], syn._PARITY_GROUPS),
}


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_a_grouped_line_constraint(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    lines = [
        constraint.params
        for constraint in puzzle.constraints
        if constraint.type == "line"
    ]

    path, groups = _EXPECTED[name]
    assert lines == [{"relation": "grouped", "path": path, "groups": groups}]
