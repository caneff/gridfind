"""Decode behaviour of the `type 303` quadruple blocks, and `corner_to_quad`'s
own resolution of a `corner` integer to a 2x2 block's four cell addresses.

Mirrors `parity_test.py`'s decode coverage: a synthesized block decodes to
the expected `quadruple` `Constraint` per clue, a `disabled` block decodes to
nothing quietly, and several clues in one block each decode independently.
"""

from __future__ import annotations

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import constraint_link
from gridfind.sudokumaker.quadruple import corner_to_quad, quad_to_corner


@pytest.mark.parametrize(
    ("corner", "size", "expected"),
    [
        (0, 9, ["R1C1", "R1C2", "R2C1", "R2C2"]),
        (7, 9, ["R1C8", "R1C9", "R2C8", "R2C9"]),
        (8, 9, ["R2C1", "R2C2", "R3C1", "R3C2"]),
    ],
    ids=["top-left", "top-right-edge", "second-row"],
)
def test_corner_to_quad_resolves_the_2x2_block(
    corner: int, size: int, expected: list[str]
) -> None:
    assert corner_to_quad(corner, size) == expected


def test_corner_to_quad_rejects_an_out_of_bounds_corner() -> None:
    with pytest.raises(ValueError, match="corner"):
        corner_to_quad(64, 9)


def test_quad_to_corner_inverts_corner_to_quad() -> None:
    assert corner_to_quad(quad_to_corner(3, 5, 9), 9) == [
        "R3C5",
        "R3C6",
        "R4C5",
        "R4C6",
    ]


def test_quadruple_block_decodes_to_a_constraint_per_clue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link({"type": 303, "clues": [{"corner": 0, "digits": [1, 2]}]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "quadruple",
            params={"cells": ["R1C1", "R1C2", "R2C1", "R2C2"], "digits": [1, 2]},
        )
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_disabled_quadruple_block_decodes_to_nothing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        {
            "type": 303,
            "clues": [{"corner": 0, "digits": [1]}],
            "disabled": True,
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "quadruple" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_several_clues_in_one_block_decode_independently() -> None:
    payload = constraint_link(
        {
            "type": 303,
            "clues": [
                {"corner": 0, "digits": [1]},
                {"corner": 1, "digits": [2, 3]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "quadruple",
            params={"cells": ["R1C1", "R1C2", "R2C1", "R2C2"], "digits": [1]},
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "quadruple",
            params={"cells": ["R1C2", "R1C3", "R2C2", "R2C3"], "digits": [2, 3]},
        )
        in puzzle.constraints
    )
