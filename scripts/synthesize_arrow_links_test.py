"""Guards for the synthesized arrow (`type 408`) corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to one `arrow`
constraint carrying the expected bulb and shafts. The drift guard that the
committed file matches its synthesizer byte for byte lives in
`corpus_drift_test.py`, auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_arrow_links as syn

from gridfind.sudokumaker import link_to_puzzle

_ONE_SHAFT = {"bulb": ["R1C1"], "arrows": [["R1C2", "R1C3"]]}
_TWO_SHAFTS = {"bulb": ["R4C1"], "arrows": [["R1C4"], ["R2C4", "R3C1"]]}
_PILL = {"bulb": ["R2C4", "R2C5"], "arrows": [["R1C1", "R4C2", "R6C3"]]}


@pytest.mark.parametrize(
    ("name", "expected_params"),
    [
        ("found-arrow-4x4", _ONE_SHAFT),
        ("broke-arrow-4x4", _ONE_SHAFT),
        ("found-arrow-two-shafts-4x4", _TWO_SHAFTS),
        ("found-pill-arrow-6x6", _PILL),
        ("broke-pill-arrow-6x6", _PILL),
    ],
)
def test_link_decodes_to_an_arrow_constraint(
    name: str, expected_params: dict[str, object]
) -> None:
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())

    arrows = [
        constraint.params
        for constraint in puzzle.constraints
        if constraint.type == "arrow"
    ]

    assert arrows == [expected_params]


def test_corpus_covers_every_expected_stem() -> None:
    assert set(syn.CORPUS) == {
        "found-arrow-4x4",
        "broke-arrow-4x4",
        "found-arrow-two-shafts-4x4",
        "found-pill-arrow-6x6",
        "broke-pill-arrow-6x6",
    }
