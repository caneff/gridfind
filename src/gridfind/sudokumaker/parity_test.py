"""Decode behaviour of the `type 100`/`101` even/odd blocks.

Mirrors `indexing_test.py`'s decode coverage: a synthesized block decodes to
the expected `parity` `Constraint`, a `disabled` block decodes to nothing
quietly, and a block with no usable `cells` warn-drops loudly.
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


def test_even_block_decodes_to_a_parity_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 100, "cells": [0, 10]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("parity", params={"parity": "even", "cells": ["R1C1", "R2C2"]})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_odd_block_decodes_to_a_parity_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 101, "cells": [0, 10]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("parity", params={"parity": "odd", "cells": ["R1C1", "R2C2"]})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_parity_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 100, "cells": [0], "style": {"color": "#ff0000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("parity", params={"parity": "even", "cells": ["R1C1"]})
        in puzzle.constraints
    )


@pytest.mark.parametrize("wire_type", [100, 101], ids=["even", "odd"])
def test_disabled_parity_block_decodes_to_nothing_quietly(
    wire_type: int, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = constraint_link({"type": wire_type, "cells": [0], "disabled": True})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "parity" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("wire_type", [100, 101], ids=["even", "odd"])
def test_parity_block_with_no_cells_warns_and_drops(
    wire_type: int, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = constraint_link({"type": wire_type, "cells": []})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "parity" for c in puzzle.constraints)
    assert "cells" in capsys.readouterr().err


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
