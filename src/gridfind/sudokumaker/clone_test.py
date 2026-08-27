"""Decode behaviour of the `type 302` clone blocks: each group under a
block's top-level `groups` decodes to one `clone` `Constraint` carrying that
group's cell addresses, a disabled block decodes to nothing quietly, and an
empty or singleton group (no pair to equate) contributes no constraint and
no warning.
"""

from __future__ import annotations

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import constraint_link


def _clone(*groups: list[int]) -> dict[str, object]:
    return {"type": 302, "groups": [list(g) for g in groups]}


def test_clone_block_decodes_to_a_constraint_per_group(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(_clone([0, 1], [2, 3]))

    puzzle, _ = link_to_puzzle(payload)

    clones = [c for c in puzzle.constraints if c.type == "clone"]
    assert clones == [
        Constraint("clone", params={"cells": ["R1C1", "R1C2"]}),
        Constraint("clone", params={"cells": ["R1C3", "R1C4"]}),
    ]
    assert capsys.readouterr().err == ""


def test_a_group_of_more_than_two_cells_chains_pairwise(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(_clone([0, 1, 2]))

    puzzle, _ = link_to_puzzle(payload)

    clones = [c for c in puzzle.constraints if c.type == "clone"]
    assert clones == [
        Constraint("clone", params={"cells": ["R1C1", "R1C2", "R1C3"]}),
    ]
    assert capsys.readouterr().err == ""


def test_disabled_clone_block_decodes_to_nothing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    block = _clone([0, 1])
    block["disabled"] = True
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "clone" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("cells", [[], [0]], ids=["empty", "singleton"])
def test_a_group_without_a_pair_decodes_to_nothing_quietly(
    cells: list[int], capsys: pytest.CaptureFixture[str]
) -> None:
    # An empty or one-cell group has no pair to equate — it emits no clone
    # constraint and no warning, matching a real link's inert extras.
    payload = constraint_link(_clone(cells))

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "clone" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_groups_in_one_block_are_independent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Mirrors issue #732's real captured link: two 2-cell groups in the same
    # block, each its own clone pair with no relationship to the other.
    payload = constraint_link(_clone([0, 9], [1, 10]))

    puzzle, _ = link_to_puzzle(payload)

    clones = [c for c in puzzle.constraints if c.type == "clone"]
    assert clones == [
        Constraint("clone", params={"cells": ["R1C1", "R2C1"]}),
        Constraint("clone", params={"cells": ["R1C2", "R2C2"]}),
    ]
    assert capsys.readouterr().err == ""
