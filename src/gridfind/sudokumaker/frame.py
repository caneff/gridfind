"""The escape-the-grid frame peel: an `(N+2)x(N+2)` link whose real puzzle is
the inner `N x N`, rewritten to a plain inner document the rest of the decode
reads unchanged.

A setter draws an escape-the-grid puzzle on a custom grid two cells wider than
the real puzzle — a ring of scratch cells around the edge that a later ticket
fills with outside clues. The link states `width == height == maxDigit + 2`: the
frame width runs two cells past the digit domain.

`peel_escape_frame` recognises the frame and rewrites the document to the inner
`N x N` puzzle — inner cells, size `N` (domain `1..N`), and the inner sub-block
of the `type 1` region matrix as the board's boxes. Everything on the border
ring drops with a stderr warning, never a raise: the cosmetic outline art
(`type 2000`), the JSON-postproc custom constraint (`type 1000`), the
hand-drawn `Rows`/`Cols` uniqueness cages (redundant — the inner grid supplies
its own row/column distinctness once it is a real `N x N` board), and the fake
corner givens marked solver-support. A border cell no clue references is never
created.

`link_to_puzzle` runs this first and, on a frame, decodes the returned inner
document in place of the original — so the inner grid rides the same size,
domain, region, given, and uniqueness path every other classic/jigsaw link
does. One home per behavior: the peel adds no second decode, it hands the
existing one a smaller board.

This ticket peels the inner grid and drops the ring. Creating outside cells for
the border clues (Numbered Rooms and the rest) is the parent spec's next step;
the drop rule for an unreferenced border cell is permanent and carries forward.
"""

from __future__ import annotations

import sys
from typing import Any, cast

from gridfind.sudokumaker.boundary import as_int
from gridfind.sudokumaker.dropped import constraint_name

_GIVENS_TYPE = 0
_REGIONS_TYPE = 1


def peel_escape_frame(document: dict[str, object]) -> dict[str, object] | None:
    """The inner `N x N` document of an escape-the-grid frame, or `None` when
    the link is not one.

    A frame is a square link whose declared domain is two digits short of its
    width — `width == height == maxDigit + 2` — with a border ring drawn outside
    the real regions. A classic or plain custom link never matches: its domain
    spans the full width. The returned document carries the inner cells, `size`
    `N` (so the domain reads back as `1..N`), and the peeled `type 1` region
    matrix; the original stays untouched.

    Every border-ring feature drops here with a loud stderr warning — the whole
    ring is unmodeled in this ticket, so it fails loud rather than silently
    shrinking the ruleset the verdict runs under."""
    raw_puzzle = document.get("puzzle")
    if not isinstance(raw_puzzle, dict):
        return None
    puzzle_data = cast("dict[str, Any]", raw_puzzle)
    frame = _frame_size(puzzle_data)
    if frame is None:
        return None
    inner = frame - 2

    cells = puzzle_data.get("cells")
    if not isinstance(cells, list) or len(cells) != frame * frame:
        return None

    inner_constraints: list[dict[str, Any]] = [{"type": _GIVENS_TYPE}]
    matrix = _live_region_matrix(puzzle_data, frame)
    if matrix is not None:
        inner_labels = _peel_inner(matrix, frame, inner)
        ring_labels = [matrix[index] for index in _border_indices(frame, inner)]
        # "regions with id >= 0 mark the inner grid": the ring's labels sit
        # outside the drawn regions, so they share no id with the inner block. A
        # matrix that fails this is not an escape frame — leave it for the
        # ordinary reject path rather than mis-peel a genuine custom board.
        if not set(ring_labels).isdisjoint(inner_labels):
            return None
        inner_constraints.append({"type": _REGIONS_TYPE, "regions": inner_labels})

    _warn_dropped_border(puzzle_data, frame, inner)
    inner_puzzle: dict[str, object] = {
        "cells": _peel_inner(cells, frame, inner),
        "size": inner,
        "constraints": inner_constraints,
    }
    return {**document, "puzzle": inner_puzzle}


def _frame_size(puzzle_data: dict[str, Any]) -> int | None:
    """The frame width `F` when this link's declared domain is two digits short
    of its width (`width == height == maxDigit + 2`), else `None`. A link
    stating no `width` (a classic or a plain `size`-only board) is never a
    frame.

    The domain arithmetic mirrors `boundary.digit_domain`, but that function
    *raises* on a domain that does not span the width — the exact case a frame
    is — so a frame needs this non-raising probe of the same fields instead."""
    if "width" not in puzzle_data or "height" not in puzzle_data:
        return None
    width = as_int(puzzle_data["width"], "width")
    height = as_int(puzzle_data["height"], "height")
    if width != height:
        return None
    min_digit = as_int(puzzle_data.get("minDigit", 1), "minDigit")
    max_digit = as_int(puzzle_data.get("maxDigit", min_digit + width - 1), "maxDigit")
    domain = max_digit - min_digit + 1
    if width != domain + 2:
        return None
    return width


def _live_region_matrix(puzzle_data: dict[str, Any], frame: int) -> list[Any] | None:
    """The frame's enabled `type 1` region matrix as a flat row-major list, or
    `None` when the link carries no live region block (an inner Latin square) or
    the block's matrix is not the frame's `F * F` size."""
    for block in puzzle_data.get("constraints", []):
        if not isinstance(block, dict):
            continue
        if block.get("type") != _REGIONS_TYPE or block.get("disabled") is True:
            continue
        matrix = block.get("regions")
        if not isinstance(matrix, list) or len(matrix) != frame * frame:
            return None
        return matrix
    return None


def _peel_inner(seq: list[Any], frame: int, inner: int) -> list[Any]:
    """The inner `N x N` sub-block of a flat row-major `F x F` sequence (cells or
    region labels), read from the `1..N` band inside the border ring."""
    return [
        seq[(row + 1) * frame + (col + 1)]
        for row in range(inner)
        for col in range(inner)
    ]


def _border_indices(frame: int, inner: int) -> list[int]:
    """The flat row-major indices of the border ring — every cell of the `F x F`
    frame outside the inner `1..N` band."""
    return [
        index for index in range(frame * frame) if _is_border_index(index, frame, inner)
    ]


def _warn_dropped_border(puzzle_data: dict[str, Any], frame: int, inner: int) -> None:
    """Warn to stderr for every border-ring feature this ticket drops: each
    enabled constraint block that is neither givens (`type 0`) nor the peeled
    regions (`type 1`) — the cosmetic outline, the postproc constraint, the
    Rows/Cols cages — and any border cell carrying a given. Silence is the one
    forbidden response: the ring is real data the verdict runs without.

    The whole ring drops, so the warning is louder than
    `dropped.has_live_data` — that predicate reads a cosmetic-only `type 2000`
    outline as inert, but here it too is dropped puzzle content, so it warns."""
    for block in puzzle_data.get("constraints", []):
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind in (_GIVENS_TYPE, _REGIONS_TYPE) or block.get("disabled") is True:
            continue
        name = constraint_name(block) or block.get("name")
        named = f" {name!r}" if isinstance(name, str) else ""
        print(
            f"warning: escape-the-grid frame: dropping border constraint"
            f"{named} (type {kind!r}) — inner grid judged without it",
            file=sys.stderr,
        )

    cells = puzzle_data.get("cells", [])
    dropped_givens = sum(
        1
        for index, cell in enumerate(cells)
        if _is_border_index(index, frame, inner)
        and isinstance(cell, dict)
        and (cell.get("given") or cell.get("value") is not None)
    )
    if dropped_givens:
        print(
            f"warning: escape-the-grid frame: dropping {dropped_givens} border "
            "cell(s) carrying givens — inner grid judged without them",
            file=sys.stderr,
        )


def _is_border_index(index: int, frame: int, inner: int) -> bool:
    """True when a row-major frame index sits on the border ring (row/col `0` or
    `frame - 1`), not in the inner `1..N` band."""
    row, col = divmod(index, frame)
    return not (1 <= row <= inner and 1 <= col <= inner)
