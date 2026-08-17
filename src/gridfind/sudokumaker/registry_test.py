"""`registry`: the `DECODER_REGISTRY` table and the decode dispatch it drives.

The registry is what `decode_link` consults to decide what each wire type is —
structural (givens/regions), a modeled constraint, or unmodeled — and how to
build each modeled type's `Constraint`s. This file pins the global-toggle
handler's round trip through the table; the drop policy the table also feeds
(`warn_on_dropped_constraints`, `has_live_data`, `constraint_name`) is pinned
in `dropped_test.py`.
"""

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import decode_link, document_to_link
from gridfind.sudokumaker.conftest import EMPTY_CELLS, WIRE_CONSTRAINTS


@pytest.mark.parametrize(
    ("block", "constraint_type"),
    [
        pytest.param({"type": 12}, "anti-king", id="anti-king"),
        pytest.param({"type": 13}, "anti-knight", id="anti-knight"),
        # The real diagonal blocks carry a cosmetic `style` alongside the type;
        # it is purely visual, so the toggle still decodes to its constraint.
        pytest.param(
            {"type": 10, "style": {"color": "#34bbe6ff", "thickness": 0.02}},
            "negative-diagonal",
            id="negative-diagonal",
        ),
        pytest.param(
            {"type": 11, "style": {"color": "#34bbe6ff", "thickness": 0.02}},
            "positive-diagonal",
            id="positive-diagonal",
        ),
    ],
)
def test_global_toggle_round_trips_through_encode_and_decode(
    block: dict[str, object], constraint_type: str
) -> None:
    # Each global toggle decodes to its gridfind constraint, and document_to_link
    # reverses it: a document carrying the wire block survives encode -> decode
    # with the matching Constraint present.
    document: dict[str, object] = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": EMPTY_CELLS, "constraints": [*WIRE_CONSTRAINTS, block]},
    }

    puzzle, _ = decode_link(document_to_link(document))

    assert Constraint(type=constraint_type) in puzzle.constraints
