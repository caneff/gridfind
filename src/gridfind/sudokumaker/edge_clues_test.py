"""`edge_clues`: the between-cells clues — XV (type 202), white kropki (200),
black kropki (201) — and the `_edge_to_pair` primitive they share.

`_edge_to_pair` inverts SudokuMaker's edge index to the orthogonally-adjacent
cell pair it names; it is this module's own transform seam, tested directly.
Each clue family decodes through `decode_link` to its gridfind constraint, and
a negative list warns loud while keeping the positive clues.
"""

import pytest
from hypothesis import given as hyp_given
from hypothesis import strategies as st

from gridfind.cell_geometry import cell_address
from gridfind.puzzle import Constraint
from gridfind.sudokumaker import decode_link
from gridfind.sudokumaker.conftest import constraint_link
from gridfind.sudokumaker.edge_clues import _edge_to_pair


@pytest.mark.parametrize(
    ("edge", "expected"),
    [
        (70, ("R4C8", "R5C8")),
        (103, ("R6C5", "R7C5")),
        (75, ("R5C3", "R5C4")),
        (132, ("R8C6", "R8C7")),
    ],
    ids=["x-vertical", "v-vertical", "kropki-horizontal-75", "kropki-horizontal-132"],
)
def test_edge_to_pair_oracle_cases(edge: int, expected: tuple[str, str]) -> None:
    # Verified against a real link during design: all four fit the two
    # closed-form formulas exactly on a 9x9 board.
    assert _edge_to_pair(edge, size=9) == expected


@st.composite
def _valid_edges(draw: st.DrawFn) -> tuple[int, int, str, int, int]:
    """A `(size, edge, orientation, r0, c0)` tuple where `edge` is a real,
    in-bounds edge of that orientation on a `size`x`size` board, and `r0, c0`
    is the 0-indexed source cell the edge names — built from the same
    closed-form formulas `_edge_to_pair` inverts, so every draw is valid by
    construction and carries its own expected answer."""
    size = draw(st.integers(min_value=2, max_value=15))
    orientation = draw(st.sampled_from(["horizontal", "vertical"]))
    if orientation == "horizontal":
        r0 = draw(st.integers(min_value=0, max_value=size - 1))
        c0 = draw(st.integers(min_value=0, max_value=size - 2))
        edge = 2 * size * r0 + c0 + 1
    else:
        r0 = draw(st.integers(min_value=0, max_value=size - 2))
        c0 = draw(st.integers(min_value=0, max_value=size - 1))
        edge = 2 * size * r0 + c0 + size
    return size, edge, orientation, r0, c0


@hyp_given(_valid_edges())
def test_edge_to_pair_decodes_the_exact_source_cells(
    case: tuple[int, int, str, int, int],
) -> None:
    # A pair shifted by a constant offset would still be in-bounds and
    # orthogonally adjacent, so bounds+adjacency alone can't catch it —
    # assert the exact addresses the same `r0, c0` the edge was built from.
    size, edge, orientation, r0, c0 = case

    pair = _edge_to_pair(edge, size)

    if orientation == "horizontal":
        expected = (cell_address(r0 + 1, c0 + 1), cell_address(r0 + 1, c0 + 2))
    else:
        expected = (cell_address(r0 + 1, c0 + 1), cell_address(r0 + 2, c0 + 1))
    assert pair == expected


def test_edge_to_pair_rejects_an_out_of_bounds_edge() -> None:
    # size=2's only edges are 0..7; 8 names no in-bounds pair.
    with pytest.raises(ValueError, match="edge"):
        _edge_to_pair(8, size=2)


# --- type 202 XV ---------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "edge", "alias", "cells"),
    [
        (10, 70, "x", ["R4C8", "R5C8"]),
        (5, 103, "v", ["R6C5", "R7C5"]),
        (10, 75, "x", ["R5C3", "R5C4"]),
    ],
    ids=["x-vertical", "v-vertical", "x-horizontal"],
)
def test_xv_clue_decodes_to_aliased_group_sum(
    value: int, edge: int, alias: str, cells: list[str]
) -> None:
    payload = constraint_link({"type": 202, "clues": [{"value": value, "edge": edge}]})

    puzzle, _ = decode_link(payload)

    assert Constraint(alias, params={"cells": cells}) in puzzle.constraints


def test_multiple_xv_clues_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {
            "type": 202,
            "clues": [{"value": 10, "edge": 70}, {"value": 5, "edge": 103}],
        }
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("x", params={"cells": ["R4C8", "R5C8"]}) in puzzle.constraints
    assert Constraint("v", params={"cells": ["R6C5", "R7C5"]}) in puzzle.constraints


def test_xv_negative_list_warns_but_keeps_positive_clues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        {"type": 202, "clues": [{"value": 10, "edge": 70}], "negative": [1, 2]}
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("x", params={"cells": ["R4C8", "R5C8"]}) in puzzle.constraints
    assert capsys.readouterr().err == (
        "warning: ignoring XV negative constraint — verdict computed without it\n"
    )


def test_xv_value_that_is_neither_x_nor_v_is_refused() -> None:
    # X (10) and V (5) are the only XV sums; any other labelled value names no
    # alias, so the link is refused rather than modeled as a wrong sum.
    payload = constraint_link({"type": 202, "clues": [{"value": 7, "edge": 70}]})

    with pytest.raises(ValueError, match="neither"):
        decode_link(payload)


# --- type 200 white kropki ----------------------------------------------


@pytest.mark.parametrize(
    ("value", "edge", "cells"),
    [
        (1, 75, ["R5C3", "R5C4"]),
        (1, 132, ["R8C6", "R8C7"]),
        (1, 70, ["R4C8", "R5C8"]),
    ],
    ids=["white-horizontal-75", "white-horizontal-132", "white-vertical-70"],
)
def test_kropki_clue_decodes_to_pair_difference(
    value: int, edge: int, cells: list[str]
) -> None:
    payload = constraint_link({"type": 200, "clues": [{"value": value, "edge": edge}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": cells, "diff": value})
        in puzzle.constraints
    )


def test_kropki_honors_a_labelled_non_one_value() -> None:
    # A white dot labelled with a difference other than 1 is honored verbatim —
    # never silently treated as the consecutive (diff 1) default.
    payload = constraint_link({"type": 200, "clues": [{"value": 3, "edge": 75}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 3})
        in puzzle.constraints
    )


def test_multiple_kropki_clues_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {
            "type": 200,
            "clues": [{"value": 1, "edge": 75}, {"value": 1, "edge": 132}],
        }
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 1})
        in puzzle.constraints
    )
    assert (
        Constraint("pair-difference", params={"cells": ["R8C6", "R8C7"], "diff": 1})
        in puzzle.constraints
    )


def test_kropki_negative_list_warns_but_keeps_positive_clues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        {"type": 200, "clues": [{"value": 1, "edge": 75}], "negative": [1, 2]}
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 1})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == (
        "warning: ignoring white-kropki negative constraint "
        "— verdict computed without it\n"
    )


# --- type 201 black kropki -----------------------------------------------


@pytest.mark.parametrize(
    ("value", "edge", "cells"),
    [
        (2, 75, ["R5C3", "R5C4"]),
        (2, 132, ["R8C6", "R8C7"]),
        (2, 70, ["R4C8", "R5C8"]),
    ],
    ids=["black-horizontal-75", "black-horizontal-132", "black-vertical-70"],
)
def test_black_kropki_clue_decodes_to_pair_ratio(
    value: int, edge: int, cells: list[str]
) -> None:
    payload = constraint_link({"type": 201, "clues": [{"value": value, "edge": edge}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": cells, "k": value})
        in puzzle.constraints
    )


def test_black_kropki_honors_a_labelled_non_two_value() -> None:
    # A black dot labelled with a ratio other than 2 is honored verbatim —
    # never silently treated as the default 2:1.
    payload = constraint_link({"type": 201, "clues": [{"value": 3, "edge": 75}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 3})
        in puzzle.constraints
    )


def test_multiple_black_kropki_clues_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {
            "type": 201,
            "clues": [{"value": 2, "edge": 75}, {"value": 2, "edge": 132}],
        }
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 2})
        in puzzle.constraints
    )
    assert (
        Constraint("pair-ratio", params={"cells": ["R8C6", "R8C7"], "k": 2})
        in puzzle.constraints
    )


def test_black_kropki_negative_list_warns_but_keeps_positive_clues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        {"type": 201, "clues": [{"value": 2, "edge": 75}], "negative": [1, 2]}
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 2})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == (
        "warning: ignoring black-kropki negative constraint "
        "— verdict computed without it\n"
    )


def test_black_kropki_non_integer_value_raises_at_decode() -> None:
    # A non-integer wire value must never model a wrong verdict — refuse the
    # link instead.
    payload = constraint_link({"type": 201, "clues": [{"value": 2.5, "edge": 75}]})

    with pytest.raises(ValueError, match="black-kropki value"):
        decode_link(payload)


# --- disabled / empty is a quiet no-op for each edge-clue family ---------


@pytest.mark.parametrize(
    ("block", "decoded_types"),
    [
        pytest.param(
            {"type": 202, "clues": [{"value": 10, "edge": 70}], "disabled": True},
            ("x", "v", "group-sum"),
            id="xv-disabled",
        ),
        pytest.param(
            {"type": 202, "clues": [], "negative": []},
            ("x", "v", "group-sum"),
            id="xv-empty",
        ),
        pytest.param(
            {"type": 200, "clues": [{"value": 1, "edge": 75}], "disabled": True},
            ("pair-difference",),
            id="kropki-disabled",
        ),
        pytest.param(
            {"type": 200, "clues": [], "negative": []},
            ("pair-difference",),
            id="kropki-empty",
        ),
    ],
)
def test_disabled_or_empty_edge_clue_block_decodes_to_nothing_quietly(
    block: dict[str, object],
    decoded_types: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A disabled block (setter switched it off) and an empty one (no clues) both
    # add no constraint and warn nothing.
    puzzle, _ = decode_link(constraint_link(block))

    assert all(c.type not in decoded_types for c in puzzle.constraints)
    assert capsys.readouterr().err == ""
