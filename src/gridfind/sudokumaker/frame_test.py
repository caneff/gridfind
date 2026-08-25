"""The escape-the-grid frame peel: an `(N+2)x(N+2)` link whose domain is `1..N`
decodes as the inner `N x N` puzzle, with a border-touching kropki dot kept as
an outside-cell constraint and the rest of the ring dropped.

A setter draws an escape-the-grid puzzle on a custom grid two cells wider than
the real puzzle, a ring of scratch cells around the edge. The link states
`width == height == maxDigit + 2`. gridfind reads the inner `N x N` as the real
puzzle — domain `1..N`, drawn regions as its boxes, rows and columns distinct —
keeps a kropki dot that touches the border ring as a `pair-difference`/
`pair-ratio` constraint over the padded outside-cell address, and drops
everything else on the ring with a warning, never a raise.
"""

import io
import re
from typing import cast

import pytest

from gridfind import cli
from gridfind.cell_geometry import row_col_to_index
from gridfind.puzzle import Board, Constraint, Given
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import (
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    encode_document,
    regions_for,
)

# A valid 6x6 solution (2-row by 3-col boxes) — an independent known-good grid,
# not one the decoder computes. Flattened row-major for the wire.
_INNER_ROWS = [
    [1, 2, 3, 4, 5, 6],
    [4, 5, 6, 1, 2, 3],
    [2, 3, 1, 5, 6, 4],
    [5, 6, 4, 2, 3, 1],
    [3, 1, 2, 6, 4, 5],
    [6, 4, 5, 3, 1, 2],
]
_INNER_SOLUTION = [digit for row in _INNER_ROWS for digit in row]


def frame_link(
    *,
    inner_solution: list[int] | None = None,
    inner_regions: list[int] | None = None,
    corner_givens: bool = True,
    cosmetic: bool = True,
    postproc: bool = True,
    rowcol_cages: bool = True,
    border_ring: bool = True,
    extra_constraints: list[dict[str, object]] | None = None,
) -> str:
    """A synthesised escape-the-grid link: an `8x8` frame (`maxDigit 6`) whose
    inner `6x6` carries `inner_solution` (all given when supplied), boxed by
    `inner_regions` (the standard 2x3 tiling by default). The border ring holds
    the scaffolding a real link carries and this ticket drops: cosmetic outline
    art (`type 2000`), a JSON-postproc custom constraint (`type 1000`),
    hand-drawn `Rows`/`Cols` uniqueness cages (`type 2001`), and fake corner
    givens marked solver-support. Each is toggled off to isolate its drop.

    `border_ring=False` fills the ring's region labels with an inner id instead
    of the `-1` sentinel, so the ring is not drawn outside the regions — the
    link is frame-shaped but not an escape frame. `extra_constraints` rides
    onto the wire `constraints` list verbatim — a border kropki test's own
    `type 200`/`201` block, decoded against this helper's fixed `8x8` frame."""
    frame, inner = 8, 6
    if inner_regions is None:
        inner_regions = regions_for(inner, 2, 3)
    cells: list[dict[str, object]] = [{} for _ in range(frame * frame)]
    matrix: list[int] = [(-1 if border_ring else 0)] * (frame * frame)
    for row in range(inner):
        for col in range(inner):
            frame_index = (row + 1) * frame + (col + 1)
            matrix[frame_index] = inner_regions[row * inner + col]
            if inner_solution is not None:
                cells[frame_index] = {
                    "given": True,
                    "value": inner_solution[row * inner + col],
                }
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": matrix},
    ]
    if rowcol_cages:
        # A custom grid carries no implicit rows/columns, so the setter draws
        # them as named cages. gridfind reads uniqueness from the inner grid
        # itself, so these are redundant and drop.
        top_row = [frame + col + 1 for col in range(inner)]
        left_col = [(row + 1) * frame + 1 for row in range(inner)]
        constraints.append(
            {"name": "Rows", "type": 2001, "cages": [{"cells": top_row}]}
        )
        constraints.append(
            {"name": "Cols", "type": 2001, "cages": [{"cells": left_col}]}
        )
    if cosmetic:
        constraints.append({"type": 2000, "lines": [[{"x": 0, "y": 0}]]})
    if postproc:
        constraints.append(
            {
                "type": 1000,
                "definition": {"name": "Postproc"},
                "input": {"groups": [{"cells": [0, 7]}]},
            }
        )
    if corner_givens:
        for corner in (0, frame - 1, frame * (frame - 1), frame * frame - 1):
            cells[corner] = {"given": True, "value": 1}
    if extra_constraints is not None:
        constraints.extend(extra_constraints)
    return encode_document(
        {
            "cells": cells,
            "width": frame,
            "height": frame,
            "minDigit": 1,
            "maxDigit": inner,
            "constraints": constraints,
        }
    )


def test_inner_grid_peels_to_an_n_by_n_board_with_domain_one_to_n() -> None:
    # The 8x8 frame with domain 1..6 was rejected as non-classic. It now decodes
    # as the inner 6x6 board with digit domain 1..6, not the frame's width.
    puzzle, _ = link_to_puzzle(frame_link())

    assert puzzle.board == Board(size=6)


def test_inner_regions_decode_as_boxes_and_rows_cols_are_distinct() -> None:
    # The inner 2x3 region tiling is the board's boxes; rows and columns are
    # distinct from treating the inner grid as a real grid, not from the
    # hand-drawn Rows/Cols cages (which drop).
    puzzle, _ = link_to_puzzle(frame_link())

    assert puzzle.constraints == (
        Constraint("rows-distinct"),
        Constraint("cols-distinct"),
        Constraint("regions-distinct"),
    )


def test_inner_givens_are_honored_and_border_givens_are_not() -> None:
    puzzle, _ = link_to_puzzle(frame_link(inner_solution=_INNER_SOLUTION))

    assert Given("R1C1", 1) in puzzle.givens
    assert len(puzzle.givens) == 36  # the 36 inner cells, not the 4 corners


def test_inner_jigsaw_regions_ride_onto_params() -> None:
    # A non-box inner tiling carries its own matrix onto params["regions"], as a
    # plain jigsaw link does — peeled from the frame's inner sub-block.
    standard = regions_for(6, 2, 3)
    jigsaw = [standard[3], *standard[1:]]  # R1C1 moved into R1C4's box
    puzzle, _ = link_to_puzzle(frame_link(inner_regions=jigsaw))

    regions = next(c for c in puzzle.constraints if c.type == "regions-distinct")
    assert regions.params["regions"] == jigsaw


def test_border_scaffolding_drops_with_warnings_not_a_raise(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link_to_puzzle(frame_link(inner_solution=_INNER_SOLUTION))

    err = capsys.readouterr().err
    assert "type 2000" in err  # cosmetic outline
    assert "type 1000" in err  # postproc
    assert "'Rows'" in err
    assert "'Cols'" in err
    assert "border cell(s) carrying givens" in err
    # Every border drop rides the one shared warn_dropped suffix.
    assert "verdict computed without it" in err


def test_a_clean_inner_frame_warns_about_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # With the scaffolding stripped, a bare frame decodes silently — the peel
    # never invents a warning for a ring that carries nothing.
    link_to_puzzle(
        frame_link(
            corner_givens=False, cosmetic=False, postproc=False, rowcol_cages=False
        )
    )

    assert capsys.readouterr().err == ""


def test_a_plain_classic_link_is_not_peeled() -> None:
    # A classic 9x9 (no width, domain spans the board) is not a frame — the peel
    # leaves it alone and it decodes as a 9x9.
    payload = encode_document({"cells": EMPTY_CELLS, "constraints": WIRE_CONSTRAINTS})
    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.board == Board(size=9)


def test_a_frame_shaped_link_without_a_border_ring_is_not_peeled() -> None:
    # The dimension relation alone is not enough: a region matrix whose ring
    # shares the inner ids is not drawn outside the regions, so the link is not
    # an escape frame. It falls through to the ordinary reject, not a mis-peel.
    with pytest.raises(ValueError, match=re.escape("domain 1..6 is not 8 digits")):
        link_to_puzzle(frame_link(border_ring=False))


def test_cli_main_returns_found_on_a_consistent_bordered_puzzle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The whole capability, at its highest seam: a bordered inner-only puzzle
    # that once rejected as non-classic now runs through cli.main to found.
    code = cli.main([frame_link(inner_solution=_INNER_SOLUTION)], io.StringIO())

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def test_cli_main_returns_broke_when_an_inner_relation_is_violated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The same puzzle with one inner given mutated to duplicate a digit in its
    # row (R1C2 set to 1, matching R1C1) breaks inner row uniqueness — broke.
    broken = list(_INNER_SOLUTION)
    broken[1] = 1
    code = cli.main([frame_link(inner_solution=broken)], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out.split("\n")[0] == "broke"


# Edges against the helper's fixed 8x8 frame, each shifted down to its padded
# outside-cell pair by hand (verified independently of the decoder via
# `edge_clues.edge_to_pair` + a manual -1 shift): edge 11 is R0C3-R1C3
# (border-inner, vertical), edge 3 is R0C2-R0C3 (border-border, horizontal,
# sharing R0C3 with edge 11), edge 13 is R0C5-R1C5 (border-inner, vertical,
# whose inner endpoint the fixture's own solution sets to 5), and edge 18 is
# R1C1-R1C2 (fully interior).
_BORDER_INNER_EDGE = 11
_BORDER_BORDER_EDGE = 3
_BORDER_INNER_EDGE_AT_A_FIVE = 13
_INTERIOR_EDGE = 18


def _black_kropki(
    edge: int, value: int, *, negative: list[int] | None = None
) -> dict[str, object]:
    block: dict[str, object] = {"type": 201, "clues": [{"value": value, "edge": edge}]}
    if negative is not None:
        block["negative"] = negative
    return block


def _white_kropki(edge: int, value: int) -> dict[str, object]:
    return {"type": 200, "clues": [{"value": value, "edge": edge}]}


def test_a_border_touching_black_kropki_dot_becomes_a_pair_ratio_constraint() -> None:
    # The real link's black kropki dots tying a border cell to its inner
    # neighbour, decoded onto the padded outside-cell address rather than
    # dropped with the rest of the ring.
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_black_kropki(_BORDER_INNER_EDGE, 2)],
    )

    puzzle, _ = link_to_puzzle(link)

    assert (
        Constraint("pair-ratio", params={"cells": ["R0C3", "R1C3"], "k": 2})
        in puzzle.constraints
    )


def test_a_border_touching_white_kropki_dot_becomes_a_pair_difference_constraint() -> (
    None
):
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_white_kropki(_BORDER_BORDER_EDGE, 1)],
    )

    puzzle, _ = link_to_puzzle(link)

    assert (
        Constraint("pair-difference", params={"cells": ["R0C2", "R0C3"], "diff": 1})
        in puzzle.constraints
    )


def test_two_border_kropki_dots_on_the_same_outside_cell_both_decode() -> None:
    # Two clues/decorations on one outside cell both bind — neither is
    # orphaned: R0C3 is named by both a white dot (to its border neighbour
    # R0C2) and a black dot (to its inner neighbour R1C3).
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[
            _white_kropki(_BORDER_BORDER_EDGE, 1),
            _black_kropki(_BORDER_INNER_EDGE, 2),
        ],
    )

    puzzle, _ = link_to_puzzle(link)

    assert (
        Constraint("pair-difference", params={"cells": ["R0C2", "R0C3"], "diff": 1})
        in puzzle.constraints
    )
    assert (
        Constraint("pair-ratio", params={"cells": ["R0C3", "R1C3"], "k": 2})
        in puzzle.constraints
    )


def test_a_kropki_dot_that_touches_no_border_cell_still_drops_with_a_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_black_kropki(_INTERIOR_EDGE, 2)],
    )

    puzzle, _ = link_to_puzzle(link)

    pair_types = ("pair-difference", "pair-ratio")
    assert not any(c.type in pair_types for c in puzzle.constraints)
    err = capsys.readouterr().err
    assert "interior kropki clue" in err
    assert "verdict computed without it" in err


def test_a_border_kropki_blocks_negative_list_drops_with_a_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_black_kropki(_BORDER_INNER_EDGE, 2, negative=[3])],
    )

    puzzle, _ = link_to_puzzle(link)

    # The positive dot still binds...
    assert (
        Constraint("pair-ratio", params={"cells": ["R0C3", "R1C3"], "k": 2})
        in puzzle.constraints
    )
    # ...but no negated pair-ratio rides in from the unmodeled negative list.
    assert not any(
        c.type == "pair-ratio" and c.params.get("negate") for c in puzzle.constraints
    )
    err = capsys.readouterr().err
    assert "negative-space rule" in err
    assert "verdict computed without it" in err


def test_a_corner_is_never_created_when_a_border_dot_names_its_neighbour() -> None:
    # The corner R0C0 sits next to R0C1 and R1C0, but no clue in this fixture
    # names it — the machinery must not invent it as a side effect of
    # decoding a neighbouring border dot.
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_white_kropki(_BORDER_BORDER_EDGE, 1)],
    )

    puzzle, _ = link_to_puzzle(link)

    cells = {
        cell
        for c in puzzle.constraints
        for cell in cast("list[str]", c.params.get("cells", []))
    }
    assert "R0C0" not in cells


def test_cli_main_found_when_a_border_kropki_dot_is_consistent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # R1C3's given is 3; a ratio-2 dot to its outside neighbour R0C3 is
    # satisfied by R0C3 = 6, the only value in 1..6 at ratio 2 from 3. Column
    # C3 already holds a 6 of its own (R2C3) — outside cells sit outside
    # inner-grid uniqueness, so the repeat is not, by itself, broke.
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_black_kropki(_BORDER_INNER_EDGE, 2)],
    )

    code = cli.main([link], io.StringIO())

    out = capsys.readouterr().out.split("\n")
    assert code == 0
    assert out[0] == "found"
    # The witness renders the border ring: R0C3's forced 6 prints on the
    # line above the box, aligned under its column.
    assert "6" in out[1]


def test_cli_main_broke_when_two_border_kropki_dots_on_one_outside_cell_conflict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Two clues bind the one shared outside cell R0C4, neither orphaning the
    # other: a black dot to inner R1C4 (given 4) forces R0C4 = 2 (ratio 2's
    # only valid partner of 4); a white dot to border neighbour R0C3 forces
    # {R0C3, R0C4} = {1, 6} (the only pair 5 apart in 1..6), so R0C4 in
    # {1, 6}. The two demands share no value — broke only because both
    # rules are live against the one cell at once. Either alone is
    # satisfiable (a black-only or white-only link on this same fixture
    # would read found), so this is not just one clue's own contradiction.
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[
            _black_kropki(12, 2),  # R0C4 - R1C4 (given 4), ratio 2 -> R0C4 = 2
            _white_kropki(4, 5),  # R0C3 - R0C4, diff 5 -> R0C4 in {1, 6}
        ],
    )

    code = cli.main([link], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out.split("\n")[0] == "broke"


def test_cli_main_broke_when_a_border_kropki_dot_has_no_valid_partner(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # R1C5's given is 5, whose only ratio-2 partners (10, 2.5) both fall
    # outside 1..6 — the outside cell has nothing it can hold, broke.
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_black_kropki(_BORDER_INNER_EDGE_AT_A_FIVE, 2)],
    )

    code = cli.main([link], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out.split("\n")[0] == "broke"


# Numbered Rooms: a `type 1000` custom constraint named `Numbered Rooms`
# whose `input.groups` each carry one group's raw cell indices — head the
# outside cell, tail its line ordered from the clue inward (the issue's own
# spec for `CustomIndexComponent`). The fixture below marks the top border
# above inner column 3: frame column 4 (`3 + 1`, the padding), frame rows
# `1..7` (row 1 the outside cell, rows `2..7` the six inner cells).
_NUMBERED_ROOMS_FRAME_COL = 4


def _numbered_rooms_group(inner_col: int) -> list[int]:
    """The raw frame-relative cell indices of the top-border Numbered Rooms
    group above `inner_col` (1-based) on the fixture's fixed `8x8` frame:
    the outside cell (frame row 1) followed by the six inner cells (frame
    rows 2..7), same frame column throughout."""
    frame_col = inner_col + 1
    return [row_col_to_index(row, frame_col, 8) for row in range(1, 8)]


def _numbered_rooms_block(*groups: list[int]) -> dict[str, object]:
    return {
        "type": 1000,
        "definition": {"name": "Numbered Rooms"},
        "input": {"groups": [{"cells": cells} for cells in groups]},
    }


def test_a_numbered_rooms_group_becomes_a_numbered_rooms_constraint() -> None:
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_numbered_rooms_block(_numbered_rooms_group(3))],
    )

    puzzle, _ = link_to_puzzle(link)

    assert (
        Constraint(
            "numbered-rooms",
            params={"cells": ["R0C3", "R1C3", "R2C3", "R3C3", "R4C3", "R5C3", "R6C3"]},
        )
        in puzzle.constraints
    )


def test_a_disabled_numbered_rooms_block_decodes_to_nothing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    block = _numbered_rooms_block(_numbered_rooms_group(3))
    block["disabled"] = True
    link = frame_link(inner_solution=_INNER_SOLUTION, extra_constraints=[block])

    puzzle, _ = link_to_puzzle(link)

    assert all(c.type != "numbered-rooms" for c in puzzle.constraints)
    assert "Numbered Rooms" not in capsys.readouterr().err


def test_a_numbered_rooms_group_whose_head_is_not_a_border_cell_drops_with_a_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A group built from frame rows 2..8 (instead of 1..7) never touches the
    # border ring — malformed data the decode cannot read as a Numbered
    # Rooms relation, so it warns rather than silently modeling nothing.
    interior_only = [row_col_to_index(row, 4, 8) for row in range(2, 9)]
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_numbered_rooms_block(interior_only)],
    )

    puzzle, _ = link_to_puzzle(link)

    assert all(c.type != "numbered-rooms" for c in puzzle.constraints)
    assert "Numbered Rooms" in capsys.readouterr().err


def test_cli_main_found_when_a_numbered_rooms_group_is_consistent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Column 3's line, near to far (R1C3..R6C3), is [3, 6, 1, 4, 2, 5]. The
    # near cell (3) names position 3, whose cell (R3C3) holds 1 — the
    # outside cell R0C3 is forced to 1.
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[_numbered_rooms_block(_numbered_rooms_group(3))],
    )

    code = cli.main([link], io.StringIO())

    out = capsys.readouterr().out.split("\n")
    assert code == 0
    assert out[0] == "found"
    assert "1" in out[1]


def test_cli_main_broke_when_a_numbered_rooms_group_conflicts_with_a_kropki_dot(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The Numbered Rooms group above forces R0C3 = 1 (see the found test).
    # A black-kropki ratio-2 dot to R1C3 (given 3) instead demands R0C3 = 6
    # (3 x 2, R0C3's only in-range ratio-2 partner) — two live rules on the
    # one shared outside cell (CONTEXT.md, "two clues bind the one cell"),
    # neither orphaning the other, that share no value.
    link = frame_link(
        inner_solution=_INNER_SOLUTION,
        extra_constraints=[
            _numbered_rooms_block(_numbered_rooms_group(3)),
            _black_kropki(_BORDER_INNER_EDGE, 2),
        ],
    )

    code = cli.main([link], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out.split("\n")[0] == "broke"
