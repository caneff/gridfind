"""Decode behaviour of the `type 16` window-groups blocks: each enabled
block decodes to its own `window-groups` `Constraint` carrying `groups`
verbatim, a disabled block decodes to nothing quietly, two blocks decode to
two constraints, and a block missing `groups` raises `KeyError` — a bare
subscript, never defaulted, the same posture `whisper_constraints` takes for
its own `minDifference`.
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


def test_a_window_groups_block_decodes_with_groups_verbatim() -> None:
    payload = constraint_link({"type": 16, "groups": [3, 12]})

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("window-groups", params={"groups": [3, 12]}) in puzzle.constraints


def test_a_disabled_window_groups_block_decodes_to_nothing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    block: dict[str, object] = {"type": 16, "groups": [3, 12], "disabled": True}
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "window-groups" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_two_window_groups_blocks_decode_to_two_constraints() -> None:
    # Entropy and mod together, e.g. — a link naming both enforces both.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"type": 16, "groups": [0b1110, 0b1110000]},
                {"type": 16, "groups": [0b1010101010, 0b0101010100]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    window_groups = [c for c in puzzle.constraints if c.type == "window-groups"]
    assert window_groups == [
        Constraint("window-groups", params={"groups": [0b1110, 0b1110000]}),
        Constraint("window-groups", params={"groups": [0b1010101010, 0b0101010100]}),
    ]


def test_a_window_groups_block_missing_groups_raises() -> None:
    payload = constraint_link({"type": 16})

    with pytest.raises(KeyError):
        link_to_puzzle(payload)
