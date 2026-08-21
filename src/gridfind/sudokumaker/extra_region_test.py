"""Decode behaviour of the `type 305` extra-region block (windoku).

Mirrors `indexing_test.py`'s decode coverage: a synthesized block decodes to
the expected `extra-region` `Constraint`, a `disabled` block decodes to
nothing quietly, and a block with no usable `cells` warn-drops loudly.
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


def test_extra_region_block_decodes_to_an_extra_region_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 305, "cells": [0, 10, 20, 30]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("extra-region", params={"cells": ["R1C1", "R2C2", "R3C3", "R4C4"]})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_extra_region_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 305, "cells": [0], "style": {"color": "#ff0000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("extra-region", params={"cells": ["R1C1"]}) in puzzle.constraints


def test_disabled_extra_region_block_decodes_to_nothing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 305, "cells": [0], "disabled": True})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "extra-region" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_extra_region_block_with_no_cells_warns_and_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 305, "cells": []})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "extra-region" for c in puzzle.constraints)
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
