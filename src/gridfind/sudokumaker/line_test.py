"""Decode behaviour of the line-clue family's wire blocks: `type 400`
(renban), `type 401` (whisper), `type 402` (palindrome), `type 403`
(between), `type 404` (region-sum), `type 406` (grouped), and `type 407`
(lockout) — seven rows of the nine-relation family (spec #672), sharing
`_line_constraints`' walk (`sudokumaker/line.py`).

Mirrors `cages_test.py`'s thermo decode coverage: a path's raw indices decode
to an addressed `line` `Constraint` carrying `relation` (plus `minDifference`
for whisper, `groups` for grouped, and `singleRegionTotals` for region-sum —
renban, palindrome, between, and lockout state no extra param), a `disabled`
block decodes to nothing quietly, an empty `lines` list adds nothing, and
several paths in one block each decode independently.
"""

from __future__ import annotations

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import constraint_link, mask


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


def test_renban_block_decodes_to_an_ordered_path_constraint() -> None:
    payload = constraint_link({"type": 400, "lines": [[0, 1, 2]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "renban", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )


def test_multiple_renban_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link({"type": 400, "lines": [[0, 1, 2], [9, 18, 27]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "renban", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "line",
            params={"relation": "renban", "path": ["R2C1", "R3C1", "R4C1"]},
        )
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "block",
    [
        pytest.param({"type": 400, "lines": [[0, 1]], "disabled": True}, id="disabled"),
        pytest.param({"type": 400, "lines": []}, id="empty-lines"),
    ],
)
def test_disabled_or_empty_renban_block_decodes_to_nothing_quietly(
    block: dict[str, object],
) -> None:
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "line" for c in puzzle.constraints)


def test_renban_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 400, "lines": [[0, 1]], "style": {"color": "#000000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("line", params={"relation": "renban", "path": ["R1C1", "R1C2"]})
        in puzzle.constraints
    )


def test_palindrome_block_decodes_to_an_ordered_path_constraint() -> None:
    payload = constraint_link({"type": 402, "lines": [[0, 1, 2]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "palindrome", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )


def test_multiple_palindrome_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link({"type": 402, "lines": [[0, 1, 2], [9, 18, 27]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "palindrome", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "line",
            params={"relation": "palindrome", "path": ["R2C1", "R3C1", "R4C1"]},
        )
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "block",
    [
        pytest.param({"type": 402, "lines": [[0, 1]], "disabled": True}, id="disabled"),
        pytest.param({"type": 402, "lines": []}, id="empty-lines"),
    ],
)
def test_disabled_or_empty_palindrome_block_decodes_to_nothing_quietly(
    block: dict[str, object],
) -> None:
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "line" for c in puzzle.constraints)


def test_palindrome_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 402, "lines": [[0, 1]], "style": {"color": "#000000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("line", params={"relation": "palindrome", "path": ["R1C1", "R1C2"]})
        in puzzle.constraints
    )


def test_between_block_decodes_to_an_ordered_path_constraint() -> None:
    payload = constraint_link({"type": 403, "lines": [[0, 1, 2]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "between", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )


def test_multiple_between_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link({"type": 403, "lines": [[0, 1, 2], [9, 18, 27]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "between", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "line",
            params={"relation": "between", "path": ["R2C1", "R3C1", "R4C1"]},
        )
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "block",
    [
        pytest.param({"type": 403, "lines": [[0, 1]], "disabled": True}, id="disabled"),
        pytest.param({"type": 403, "lines": []}, id="empty-lines"),
    ],
)
def test_disabled_or_empty_between_block_decodes_to_nothing_quietly(
    block: dict[str, object],
) -> None:
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "line" for c in puzzle.constraints)


def test_between_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 403, "lines": [[0, 1]], "style": {"color": "#000000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("line", params={"relation": "between", "path": ["R1C1", "R1C2"]})
        in puzzle.constraints
    )


def test_lockout_block_decodes_to_an_ordered_path_constraint() -> None:
    payload = constraint_link({"type": 407, "lines": [[0, 1, 2]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "lockout", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )


def test_multiple_lockout_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link({"type": 407, "lines": [[0, 1, 2], [9, 18, 27]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={"relation": "lockout", "path": ["R1C1", "R1C2", "R1C3"]},
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "line",
            params={"relation": "lockout", "path": ["R2C1", "R3C1", "R4C1"]},
        )
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "block",
    [
        pytest.param({"type": 407, "lines": [[0, 1]], "disabled": True}, id="disabled"),
        pytest.param({"type": 407, "lines": []}, id="empty-lines"),
    ],
)
def test_disabled_or_empty_lockout_block_decodes_to_nothing_quietly(
    block: dict[str, object],
) -> None:
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "line" for c in puzzle.constraints)


def test_lockout_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 407, "lines": [[0, 1]], "style": {"color": "#000000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("line", params={"relation": "lockout", "path": ["R1C1", "R1C2"]})
        in puzzle.constraints
    )


_ENTROPIC_GROUPS = [mask({1, 2, 3}), mask({4, 5, 6}), mask({7, 8, 9})]


def test_grouped_block_decodes_to_an_ordered_path_constraint() -> None:
    payload = constraint_link(
        {"type": 406, "lines": [[0, 1, 2]], "groups": _ENTROPIC_GROUPS}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "grouped",
                "path": ["R1C1", "R1C2", "R1C3"],
                "groups": _ENTROPIC_GROUPS,
            },
        )
        in puzzle.constraints
    )


def test_multiple_grouped_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {
            "type": 406,
            "lines": [[0, 1, 2], [9, 18, 27]],
            "groups": _ENTROPIC_GROUPS,
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "grouped",
                "path": ["R1C1", "R1C2", "R1C3"],
                "groups": _ENTROPIC_GROUPS,
            },
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "line",
            params={
                "relation": "grouped",
                "path": ["R2C1", "R3C1", "R4C1"],
                "groups": _ENTROPIC_GROUPS,
            },
        )
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "block",
    [
        pytest.param(
            {
                "type": 406,
                "lines": [[0, 1, 2]],
                "groups": _ENTROPIC_GROUPS,
                "disabled": True,
            },
            id="disabled",
        ),
        pytest.param(
            {"type": 406, "lines": [], "groups": _ENTROPIC_GROUPS}, id="empty-lines"
        ),
    ],
)
def test_disabled_or_empty_grouped_block_decodes_to_nothing_quietly(
    block: dict[str, object],
) -> None:
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "line" for c in puzzle.constraints)


def test_grouped_style_is_ignored() -> None:
    payload = constraint_link(
        {
            "type": 406,
            "lines": [[0, 1, 2]],
            "groups": _ENTROPIC_GROUPS,
            "style": {"color": "#000000"},
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "grouped",
                "path": ["R1C1", "R1C2", "R1C3"],
                "groups": _ENTROPIC_GROUPS,
            },
        )
        in puzzle.constraints
    )


def test_a_grouped_block_missing_groups_raises() -> None:
    payload = constraint_link({"type": 406, "lines": [[0, 1, 2]]})

    with pytest.raises(KeyError):
        link_to_puzzle(payload)


def test_region_sum_block_decodes_to_an_ordered_path_constraint() -> None:
    payload = constraint_link({"type": 404, "lines": [[0, 1, 2]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "region-sum",
                "path": ["R1C1", "R1C2", "R1C3"],
                "singleRegionTotals": False,
            },
        )
        in puzzle.constraints
    )


def test_region_sum_block_carries_its_own_single_region_totals_flag() -> None:
    payload = constraint_link(
        {"type": 404, "lines": [[0, 1]], "singleRegionTotals": True}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "region-sum",
                "path": ["R1C1", "R1C2"],
                "singleRegionTotals": True,
            },
        )
        in puzzle.constraints
    )


def test_multiple_region_sum_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link({"type": 404, "lines": [[0, 1, 2], [9, 18, 27]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "region-sum",
                "path": ["R1C1", "R1C2", "R1C3"],
                "singleRegionTotals": False,
            },
        )
        in puzzle.constraints
    )
    assert (
        Constraint(
            "line",
            params={
                "relation": "region-sum",
                "path": ["R2C1", "R3C1", "R4C1"],
                "singleRegionTotals": False,
            },
        )
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "block",
    [
        pytest.param({"type": 404, "lines": [[0, 1]], "disabled": True}, id="disabled"),
        pytest.param({"type": 404, "lines": []}, id="empty-lines"),
    ],
)
def test_disabled_or_empty_region_sum_block_decodes_to_nothing_quietly(
    block: dict[str, object],
) -> None:
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "line" for c in puzzle.constraints)


def test_region_sum_style_is_ignored() -> None:
    payload = constraint_link(
        {"type": 404, "lines": [[0, 1]], "style": {"color": "#000000"}}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "line",
            params={
                "relation": "region-sum",
                "path": ["R1C1", "R1C2"],
                "singleRegionTotals": False,
            },
        )
        in puzzle.constraints
    )
