"""Decode behaviour of the `type 401` whisper-line blocks — the first wire
type of the nine-relation line-clue family.

Mirrors `cages_test.py`'s thermo decode coverage: a path's raw indices decode
to an addressed `line` `Constraint` carrying `relation` and `minDifference`,
a `disabled` block decodes to nothing quietly, an empty `lines` list adds
nothing, and several paths in one block each decode independently.
"""

from __future__ import annotations

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import constraint_link


def test_whisper_block_decodes_to_an_ordered_path_constraint() -> None:
    payload = constraint_link({"type": 401, "lines": [[0, 1, 2]], "minDifference": 5})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "whisper",
                "path": ["R1C1", "R1C2", "R1C3"],
                "minDifference": 5,
            },
        )
        in puzzle.constraints
    )


def test_dutch_whisper_carries_its_own_threshold() -> None:
    payload = constraint_link({"type": 401, "lines": [[0, 1]], "minDifference": 4})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "whisper",
                "path": ["R1C1", "R1C2"],
                "minDifference": 4,
            },
        )
        in puzzle.constraints
    )


def test_multiple_whisper_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {"type": 401, "lines": [[0, 1, 2], [9, 18, 27]], "minDifference": 5}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "whisper",
                "path": ["R1C1", "R1C2", "R1C3"],
                "minDifference": 5,
            },
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "line",
            params={
                "relation": "whisper",
                "path": ["R2C1", "R3C1", "R4C1"],
                "minDifference": 5,
            },
        )
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "block",
    [
        pytest.param(
            {"type": 401, "lines": [[0, 1]], "minDifference": 5, "disabled": True},
            id="disabled",
        ),
        pytest.param({"type": 401, "lines": [], "minDifference": 5}, id="empty-lines"),
    ],
)
def test_disabled_or_empty_whisper_block_decodes_to_nothing_quietly(
    block: dict[str, object],
) -> None:
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "line" for c in puzzle.constraints)


def test_whisper_style_is_ignored() -> None:
    payload = constraint_link(
        {
            "type": 401,
            "lines": [[0, 1]],
            "minDifference": 5,
            "style": {"color": "#000000"},
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "whisper",
                "path": ["R1C1", "R1C2"],
                "minDifference": 5,
            },
        )
        in puzzle.constraints
    )


def test_a_whisper_block_missing_min_difference_raises() -> None:
    payload = constraint_link({"type": 401, "lines": [[0, 1]]})

    with pytest.raises(KeyError):
        link_to_puzzle(payload)
