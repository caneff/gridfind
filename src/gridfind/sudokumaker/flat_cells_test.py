"""Decode behaviour of the flat-cells clue blocks: `type 305` (extra-region),
`type 600`/`601` (row/col indexing), and `type 100`/`101` (even/odd parity).

All five share one shape through `flat_cells._flat_cells_handler`: a
synthesized block decodes to the expected `Constraint`, a `disabled` block
decodes to nothing quietly, and a block with no usable `cells` warn-drops
loudly.
"""

from __future__ import annotations

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import (
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    constraint_link,
    encode_document,
)

FLAT_CELLS_ARGNAMES = ("wire_type", "constraint_type", "extra_params")
FLAT_CELLS_CASES = [
    pytest.param(305, "extra-region", {}, id="extra-region"),
    pytest.param(600, "indexing", {"axis": "row"}, id="row-indexing"),
    pytest.param(601, "indexing", {"axis": "col"}, id="col-indexing"),
    pytest.param(100, "parity", {"parity": "even"}, id="even"),
    pytest.param(101, "parity", {"parity": "odd"}, id="odd"),
]


@pytest.mark.parametrize(FLAT_CELLS_ARGNAMES, FLAT_CELLS_CASES)
def test_block_decodes_to_the_expected_constraint(
    wire_type: int,
    constraint_type: str,
    extra_params: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": wire_type, "cells": [0, 10]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(constraint_type, params={**extra_params, "cells": ["R1C1", "R2C2"]})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(FLAT_CELLS_ARGNAMES, FLAT_CELLS_CASES)
def test_style_is_ignored(
    wire_type: int, constraint_type: str, extra_params: dict[str, str]
) -> None:
    payload = constraint_link(
        {"type": wire_type, "cells": [0], "style": {"color": "#ff0000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(constraint_type, params={**extra_params, "cells": ["R1C1"]})
        in puzzle.constraints
    )


@pytest.mark.parametrize(FLAT_CELLS_ARGNAMES, FLAT_CELLS_CASES)
def test_disabled_block_decodes_to_nothing_quietly(
    wire_type: int,
    constraint_type: str,
    extra_params: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": wire_type, "cells": [0], "disabled": True})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != constraint_type for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(FLAT_CELLS_ARGNAMES, FLAT_CELLS_CASES)
def test_block_with_no_cells_warns_and_drops(
    wire_type: int,
    constraint_type: str,
    extra_params: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": wire_type, "cells": []})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != constraint_type for c in puzzle.constraints)
    assert "cells" in capsys.readouterr().err


def test_two_extra_region_blocks_decode_to_two_constraints() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"type": 305, "cells": [0]},
                {"type": 305, "cells": [1]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    extra_regions = [c for c in puzzle.constraints if c.type == "extra-region"]
    assert Constraint("extra-region", params={"cells": ["R1C1"]}) in extra_regions
    assert Constraint("extra-region", params={"cells": ["R1C2"]}) in extra_regions


def test_row_and_col_indexing_blocks_together_decode_to_two_constraints() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"type": 600, "cells": [0]},
                {"type": 601, "cells": [1]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("indexing", params={"axis": "row", "cells": ["R1C1"]})
        in puzzle.constraints
    )
    assert (
        Constraint("indexing", params={"axis": "col", "cells": ["R1C2"]})
        in puzzle.constraints
    )


def test_even_and_odd_blocks_together_decode_to_two_constraints() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"type": 100, "cells": [0]},
                {"type": 101, "cells": [1]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("parity", params={"parity": "even", "cells": ["R1C1"]})
        in puzzle.constraints
    )
    assert (
        Constraint("parity", params={"parity": "odd", "cells": ["R1C2"]})
        in puzzle.constraints
    )
