"""`edge_clues`: the between-cells clues — XV (type 202), white kropki (200),
black kropki (201) — and the `_edge_to_pair` primitive they share.

`_edge_to_pair` inverts SudokuMaker's edge index to the orthogonally-adjacent
cell pair it names; it is this module's own transform seam, tested directly.
Each clue family decodes through `link_to_puzzle` to its gridfind constraint. All
three types' negative lists are enforced (the negative-space mechanism).
"""

import pytest
from hypothesis import given as hyp_given
from hypothesis import strategies as st

from gridfind.cell_geometry import format_address
from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import (
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    constraint_link,
    encode_document,
)
from gridfind.sudokumaker.edge_clues import _edge_to_pair
from gridfind.verdict import verdict


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
        expected = (format_address(r0 + 1, c0 + 1), format_address(r0 + 1, c0 + 2))
    else:
        expected = (format_address(r0 + 1, c0 + 1), format_address(r0 + 2, c0 + 1))
    assert pair == expected


def test_edge_to_pair_rejects_an_out_of_bounds_edge() -> None:
    # size=2's only edges are 0..7; 8 names no in-bounds pair.
    with pytest.raises(ValueError, match="edge"):
        _edge_to_pair(8, size=2)


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

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint(alias, params={"cells": cells}) in puzzle.constraints


def test_multiple_xv_clues_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {
            "type": 202,
            "clues": [{"value": 10, "edge": 70}, {"value": 5, "edge": 103}],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("x", params={"cells": ["R4C8", "R5C8"]}) in puzzle.constraints
    assert Constraint("v", params={"cells": ["R6C5", "R7C5"]}) in puzzle.constraints


def test_xv_negative_rule_forbids_every_listed_sum_over_an_unmarked_pair(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        {"type": 202, "clues": [{"value": 10, "edge": 70}], "negative": [10, 5]}
    )

    puzzle, _ = link_to_puzzle(payload)

    # The marked pair still decodes its own positive clue...
    assert Constraint("x", params={"cells": ["R4C8", "R5C8"]}) in puzzle.constraints
    # ...and an unrelated orthogonal pair elsewhere on the same board picks up
    # a negated group-sum for each listed value.
    for value in (10, 5):
        assert (
            Constraint(
                "group-sum",
                params={"cells": ["R1C1", "R1C2"], "sum": value, "negate": True},
            )
            in puzzle.constraints
        )
    assert capsys.readouterr().err == ""


def test_xv_negative_rule_exempts_the_marked_edge() -> None:
    payload = constraint_link(
        {"type": 202, "clues": [{"value": 10, "edge": 70}], "negative": [10, 5]}
    )

    puzzle, _ = link_to_puzzle(payload)

    for value in (10, 5):
        assert (
            Constraint(
                "group-sum",
                params={"cells": ["R4C8", "R5C8"], "sum": value, "negate": True},
            )
            not in puzzle.constraints
        )


def test_xv_value_that_is_neither_x_nor_v_is_refused() -> None:
    # X (10) and V (5) are the only XV sums; any other labelled value names no
    # alias, so the link is refused rather than modeled as a wrong sum.
    payload = constraint_link({"type": 202, "clues": [{"value": 7, "edge": 70}]})

    with pytest.raises(ValueError, match="neither"):
        link_to_puzzle(payload)


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

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("pair-difference", params={"cells": cells, "diff": value})
        in puzzle.constraints
    )


def test_kropki_honors_a_labelled_non_one_value() -> None:
    # A white dot labelled with a difference other than 1 is honored verbatim —
    # never silently treated as the consecutive (diff 1) default.
    payload = constraint_link({"type": 200, "clues": [{"value": 3, "edge": 75}]})

    puzzle, _ = link_to_puzzle(payload)

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

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 1})
        in puzzle.constraints
    )
    assert (
        Constraint("pair-difference", params={"cells": ["R8C6", "R8C7"], "diff": 1})
        in puzzle.constraints
    )


def test_kropki_negative_rule_forbids_every_listed_difference_over_an_unmarked_pair(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        {"type": 200, "clues": [{"value": 1, "edge": 75}], "negative": [1, 2]}
    )

    puzzle, _ = link_to_puzzle(payload)

    # The marked pair still decodes its own positive clue...
    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 1})
        in puzzle.constraints
    )
    # ...and an unrelated orthogonal pair elsewhere on the same board picks up
    # a negated pair-difference for each listed value.
    for value in (1, 2):
        assert (
            Constraint(
                "pair-difference",
                params={"cells": ["R1C1", "R1C2"], "diff": value, "negate": True},
            )
            in puzzle.constraints
        )
    assert capsys.readouterr().err == ""


def test_kropki_negative_rule_exempts_the_marked_edge() -> None:
    payload = constraint_link(
        {"type": 200, "clues": [{"value": 1, "edge": 75}], "negative": [1, 2]}
    )

    puzzle, _ = link_to_puzzle(payload)

    for value in (1, 2):
        assert (
            Constraint(
                "pair-difference",
                params={"cells": ["R5C3", "R5C4"], "diff": value, "negate": True},
            )
            not in puzzle.constraints
        )


def test_kropki_negative_rule_never_constrains_a_diagonal_pair() -> None:
    payload = constraint_link({"type": 200, "clues": [], "negative": [1]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "pair-difference",
            params={"cells": ["R1C1", "R2C2"], "diff": 1, "negate": True},
        )
        not in puzzle.constraints
    )
    assert (
        Constraint(
            "pair-difference",
            params={"cells": ["R2C2", "R1C1"], "diff": 1, "negate": True},
        )
        not in puzzle.constraints
    )


def test_kropki_negative_rule_ignores_the_inert_override_boolean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # overrideNegativeDifferences is not exposed in SudokuMaker and carries no
    # puzzle meaning — its presence must not spawn a warning or change what
    # decodes.
    payload = constraint_link(
        {
            "type": 200,
            "clues": [{"value": 1, "edge": 75}],
            "negative": [2],
            "overrideNegativeDifferences": True,
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "pair-difference",
            params={"cells": ["R1C1", "R1C2"], "diff": 2, "negate": True},
        )
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("modifier_block", "min_digit"),
    [
        pytest.param(
            {"name": "Doubler", "type": 2001, "cages": [{"value": "", "cells": [0]}]},
            None,
            id="doubler",
        ),
        pytest.param(
            {"name": "S-cell", "type": 2001, "cages": [{"cells": [0]}]}, 0, id="s-cell"
        ),
    ],
)
def test_kropki_negative_rule_composes_with_a_doubler_or_s_cell_board(
    modifier_block: dict[str, object],
    min_digit: int | None,
) -> None:
    # The negative rule reuses `differs_by`, the same value_expr-reading
    # emitter the positive clue uses, so it composes with a doubler/S-cell
    # board for free rather than refusing it as `s_blind`.
    document: dict[str, object] = {
        "cells": EMPTY_CELLS,
        "constraints": [
            *WIRE_CONSTRAINTS,
            {"type": 200, "clues": [{"value": 1, "edge": 75}], "negative": [3]},
            modifier_block,
        ],
    }
    if min_digit is not None:
        document["minDigit"] = min_digit
    payload = encode_document(document)

    puzzle, state = link_to_puzzle(payload)

    assert any(
        c.type == "pair-difference" and c.params.get("negate")
        for c in puzzle.constraints
    )
    result = verdict(puzzle, state)
    assert result.kind in ("found", "broke")


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

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("pair-ratio", params={"cells": cells, "k": value})
        in puzzle.constraints
    )


def test_black_kropki_honors_a_labelled_non_two_value() -> None:
    # A black dot labelled with a ratio other than 2 is honored verbatim —
    # never silently treated as the default 2:1.
    payload = constraint_link({"type": 201, "clues": [{"value": 3, "edge": 75}]})

    puzzle, _ = link_to_puzzle(payload)

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

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 2})
        in puzzle.constraints
    )
    assert (
        Constraint("pair-ratio", params={"cells": ["R8C6", "R8C7"], "k": 2})
        in puzzle.constraints
    )


def test_black_kropki_negative_rule_forbids_every_listed_ratio_over_an_unmarked_pair(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        {"type": 201, "clues": [{"value": 2, "edge": 75}], "negative": [3, 5]}
    )

    puzzle, _ = link_to_puzzle(payload)

    # The marked pair still decodes its own positive clue...
    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 2})
        in puzzle.constraints
    )
    # ...and an unrelated orthogonal pair elsewhere on the same board picks up
    # a negated pair-ratio for each listed value.
    for k in (3, 5):
        assert (
            Constraint(
                "pair-ratio", params={"cells": ["R1C1", "R1C2"], "k": k, "negate": True}
            )
            in puzzle.constraints
        )
    assert capsys.readouterr().err == ""


def test_black_kropki_negative_rule_exempts_the_marked_edge() -> None:
    payload = constraint_link(
        {"type": 201, "clues": [{"value": 2, "edge": 75}], "negative": [3, 5]}
    )

    puzzle, _ = link_to_puzzle(payload)

    for k in (3, 5):
        assert (
            Constraint(
                "pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": k, "negate": True}
            )
            not in puzzle.constraints
        )


def test_black_kropki_negative_rule_ignores_the_inert_override_boolean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # overrideNegativeRatios is not exposed in SudokuMaker and carries no
    # puzzle meaning — its presence must not spawn a warning or change what
    # decodes.
    payload = constraint_link(
        {
            "type": 201,
            "clues": [{"value": 2, "edge": 75}],
            "negative": [3],
            "overrideNegativeRatios": True,
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint(
            "pair-ratio",
            params={"cells": ["R1C1", "R1C2"], "k": 3, "negate": True},
        )
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("modifier_block", "min_digit"),
    [
        pytest.param(
            {"name": "Doubler", "type": 2001, "cages": [{"value": "", "cells": [0]}]},
            None,
            id="doubler",
        ),
        pytest.param(
            {"name": "S-cell", "type": 2001, "cages": [{"cells": [0]}]}, 0, id="s-cell"
        ),
    ],
)
def test_black_kropki_negative_rule_composes_with_a_doubler_or_s_cell_board(
    modifier_block: dict[str, object],
    min_digit: int | None,
) -> None:
    # The negative rule reuses `ratio_of`, the same value_expr-reading
    # emitter the positive clue uses, so it composes with a doubler/S-cell
    # board for free rather than refusing it as `s_blind`.
    document: dict[str, object] = {
        "cells": EMPTY_CELLS,
        "constraints": [
            *WIRE_CONSTRAINTS,
            {"type": 201, "clues": [{"value": 2, "edge": 75}], "negative": [3]},
            modifier_block,
        ],
    }
    if min_digit is not None:
        document["minDigit"] = min_digit
    payload = encode_document(document)

    puzzle, state = link_to_puzzle(payload)

    assert any(
        c.type == "pair-ratio" and c.params.get("negate") for c in puzzle.constraints
    )
    result = verdict(puzzle, state)
    assert result.kind in ("found", "broke")


def test_black_kropki_non_integer_value_raises_at_decode() -> None:
    # A non-integer wire value must never model a wrong verdict — refuse the
    # link instead.
    payload = constraint_link({"type": 201, "clues": [{"value": 2.5, "edge": 75}]})

    with pytest.raises(ValueError, match="black-kropki value"):
        link_to_puzzle(payload)


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
    puzzle, _ = link_to_puzzle(constraint_link(block))

    assert all(c.type not in decoded_types for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("kropki_type", "relation_type"),
    [(200, "pair-difference"), (201, "pair-ratio")],
    ids=["white", "black"],
)
@pytest.mark.parametrize(
    ("modifier_block", "min_digit"),
    [
        pytest.param(
            {"name": "Doubler", "type": 2001, "cages": [{"value": "", "cells": [0]}]},
            None,
            id="doubler",
        ),
        pytest.param(
            {"name": "S-cell", "type": 2001, "cages": [{"cells": [0]}]}, 0, id="s-cell"
        ),
    ],
)
def test_a_positive_kropki_link_composes_with_a_doubler_or_s_cell_board(
    kropki_type: int,
    relation_type: str,
    modifier_block: dict[str, object],
    min_digit: int | None,
) -> None:
    # Both kropki colours read `value_expr` (the same seam XV reads), not a
    # single content slot, so a positive kropki clue composes with a doubler
    # or S-cell marker board rather than refusing it as `s_blind`.
    document: dict[str, object] = {
        "cells": EMPTY_CELLS,
        "constraints": [
            *WIRE_CONSTRAINTS,
            {"type": kropki_type, "clues": [{"value": 1, "edge": 75}]},
            modifier_block,
        ],
    }
    if min_digit is not None:
        document["minDigit"] = min_digit
    payload = encode_document(document)

    puzzle, state = link_to_puzzle(payload)

    assert any(c.type == relation_type for c in puzzle.constraints)
    result = verdict(puzzle, state)
    assert result.kind in ("found", "broke")
