"""Decode behaviour of the `type 600`/`601` indexing blocks (the 159 clue).

Mirrors `cages_test.py`'s thermo decode coverage: a synthesized block decodes
to the expected `indexing` `Constraint`, a `disabled` block decodes to
nothing quietly, and a block with no usable `cells` warn-drops loudly
(unlike a bare thermo/cage block's quiet empty-list skip — an indexing block
carrying no marked cells is itself the anomaly the spec calls out).
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


def test_row_indexing_block_decodes_to_an_indexing_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 600, "cells": [0, 10]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("indexing", params={"axis": "row", "cells": ["R1C1", "R2C2"]})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_col_indexing_block_decodes_to_an_indexing_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 601, "cells": [0, 10]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("indexing", params={"axis": "col", "cells": ["R1C1", "R2C2"]})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_indexing_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 600, "cells": [0], "style": {"color": "#ff0000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("indexing", params={"axis": "row", "cells": ["R1C1"]})
        in puzzle.constraints
    )


@pytest.mark.parametrize("wire_type", [600, 601], ids=["row", "col"])
def test_disabled_indexing_block_decodes_to_nothing_quietly(
    wire_type: int, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = constraint_link({"type": wire_type, "cells": [0], "disabled": True})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "indexing" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("wire_type", [600, 601], ids=["row", "col"])
def test_indexing_block_with_no_cells_warns_and_drops(
    wire_type: int, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = constraint_link({"type": wire_type, "cells": []})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "indexing" for c in puzzle.constraints)
    assert "cells" in capsys.readouterr().err


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
