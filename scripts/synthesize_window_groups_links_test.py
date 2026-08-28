"""Guards for the synthesized window-groups (`type 16`) corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to one `window-groups`
constraint carrying the expected groups. The drift guard that the committed
file matches its synthesizer byte for byte lives in `corpus_drift_test.py`,
auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_window_groups_links as syn

from gridfind.sudokumaker import link_to_puzzle

_EXPECTED: dict[str, list[int]] = {
    "found-window-groups-4x4": syn._LOW_HIGH_GROUPS,
    "broke-window-groups-4x4": syn._LOW_HIGH_GROUPS,
    "found-window-groups-mod-9x9": syn._MOD_GROUPS,
    "broke-window-groups-mod-9x9": syn._MOD_GROUPS,
}


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_a_window_groups_constraint(name: str) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    window_groups = [
        constraint.params
        for constraint in puzzle.constraints
        if constraint.type == "window-groups"
    ]

    assert window_groups == [{"groups": _EXPECTED[name]}]
