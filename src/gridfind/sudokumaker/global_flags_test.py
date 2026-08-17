"""`global_flags`: the payload-less `Somedoku` global-flag component —
recognized on either name-bearing carrier, a `type 1000` custom
constraint's `definition.name` or a `type 2001` cosmetic cage's top-level
`name`, and decoded through `link_to_puzzle` to a single `line-count-distinct`
constraint in place of the classic `rows-distinct`/`cols-distinct`/
`regions-distinct` triplet. Cells and value are ignored on both carriers; a
`disabled` block on either contributes nothing.
"""

from __future__ import annotations

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import (
    CLASSIC_CONSTRAINTS,
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    constraint_link,
    encode_document,
)


def test_somedoku_custom_constraint_decodes_to_line_count_distinct() -> None:
    # `constraint_link` rides the standard `type 1` box regions alongside the
    # `Somedoku` custom constraint; the bare `line-count-distinct` result
    # proves the classic rows/cols/regions-distinct triplet is suppressed
    # even though a regions block is present — a somedoku puzzle runs on no
    # boxes at all.
    payload = constraint_link({"type": 1000, "definition": {"name": "Somedoku"}})

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.constraints == (Constraint("line-count-distinct"),)


def test_somedoku_cosmetic_cage_decodes_to_line_count_distinct() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "Somedoku", "type": 2001, "cages": [{"cells": [0, 1]}]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.constraints == (Constraint("line-count-distinct"),)


@pytest.mark.parametrize(
    "somedoku_block",
    [
        pytest.param(
            {"type": 1000, "definition": {"name": "Somedoku"}, "clues": [{"cell": 0}]},
            id="type-1000-with-live-payload",
        ),
        pytest.param(
            {
                "name": "Somedoku",
                "type": 2001,
                "cages": [{"value": "7", "cells": [0, 1, 2]}],
            },
            id="type-2001-with-cells-and-value",
        ),
    ],
)
def test_somedoku_ignores_its_own_cells_and_value(
    somedoku_block: dict[str, object],
) -> None:
    # A Somedoku block's cells and value are pure noise: whatever it carries,
    # the decode is the same bare line-count-distinct constraint, never a
    # cage/group-sum and never a warn-drop of an "active" payload.
    payload = encode_document(
        {"cells": EMPTY_CELLS, "constraints": [*WIRE_CONSTRAINTS, somedoku_block]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.constraints == (Constraint("line-count-distinct"),)


def test_somedoku_type_1000_does_not_warn_even_with_live_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A cage-shaped name (Sum/Doubler/…) warns when stranded on a type 1000
    # carrier with no cells (registry_test.py's own coverage of that
    # direction); a global-flag name needs no cells at all, so the opposite
    # holds here — recognized and decoded, never warned about, live payload
    # or not.
    payload = constraint_link(
        {
            "type": 1000,
            "definition": {"name": "Somedoku"},
            "input": {"groups": [{"cells": [0, 1]}]},
        }
    )

    link_to_puzzle(payload)

    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "somedoku_block",
    [
        pytest.param(
            {
                "type": 1000,
                "definition": {"name": "Somedoku"},
                "disabled": True,
            },
            id="type-1000",
        ),
        pytest.param(
            {"name": "Somedoku", "type": 2001, "cages": [], "disabled": True},
            id="type-2001",
        ),
    ],
)
def test_disabled_somedoku_block_decodes_to_nothing(
    somedoku_block: dict[str, object],
) -> None:
    payload = encode_document(
        {"cells": EMPTY_CELLS, "constraints": [*WIRE_CONSTRAINTS, somedoku_block]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.constraints == CLASSIC_CONSTRAINTS


def test_somedoku_still_decodes_a_registry_type_after_regions() -> None:
    # link_to_puzzle's registry loop `continue`s past `wire_type == 1` (regions)
    # for a somedoku puzzle, but must keep walking DECODER_REGISTRY afterward —
    # an anti-king toggle, which sits later in registry order, still decodes
    # alongside the line-count-distinct rule.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"type": 1000, "definition": {"name": "Somedoku"}},
                {"type": 12},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.constraints == (
        Constraint("line-count-distinct"),
        Constraint("anti-king"),
    )
