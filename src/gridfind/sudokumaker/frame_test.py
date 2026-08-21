"""The escape-the-grid frame peel: an `(N+2)x(N+2)` link whose domain is `1..N`
decodes as the inner `N x N` puzzle, with the border ring dropped.

A setter draws an escape-the-grid puzzle on a custom grid two cells wider than
the real puzzle, a ring of scratch cells around the edge. The link states
`width == height == maxDigit + 2`. gridfind reads the inner `N x N` as the real
puzzle — domain `1..N`, drawn regions as its boxes, rows and columns distinct —
and drops everything on the border ring with a warning, never a raise.
"""

import io
import re

import pytest

from gridfind import cli
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
    link is frame-shaped but not an escape frame."""
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
    # The inner given at R1C1 (value 1) survives; the fake corner givens on the
    # border ring never enter the puzzle.
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
    # The cosmetic outline (type 2000), the postproc constraint (type 1000), the
    # Rows/Cols cages (type 2001), and the corner givens all drop to stderr — no
    # raise, no silent drop.
    link_to_puzzle(frame_link(inner_solution=_INNER_SOLUTION))

    err = capsys.readouterr().err
    assert "type 2000" in err  # cosmetic outline
    assert "type 1000" in err  # postproc
    assert "'Rows'" in err
    assert "'Cols'" in err
    assert "border cell(s) carrying givens" in err


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
