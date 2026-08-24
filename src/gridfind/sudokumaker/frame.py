"""The escape-the-grid frame peel: an `(N+2)x(N+2)` link whose real puzzle is
the inner `N x N`, rewritten to a plain inner document the rest of the decode
reads unchanged, plus any border-ring outside-cell constraints the link's own
decorations name.

A setter draws an escape-the-grid puzzle on a custom grid two cells wider than
the real puzzle — a ring of scratch cells around the edge that outside clues
attach to. The link states `width == height == maxDigit + 2`: the frame width
runs two cells past the digit domain.

`peel_escape_frame` recognises the frame and returns the inner `N x N`
document — inner cells, size `N` (domain `1..N`), and the inner sub-block of
the `type 1` region matrix as the board's boxes — paired with the canonical
`Constraint`s a border-touching kropki dot (`type 200`/`201`) decodes to
against the padded outside-cell addressing (CONTEXT.md, "outside cell"; a
border row/col reads `0` or `N + 1`, never colliding with the inner `1..N`).
Everything else on the border ring drops with a stderr warning, never a
raise: the cosmetic outline art (`type 2000`), the JSON-postproc custom
constraint (`type 1000`), the hand-drawn `Rows`/`Cols` uniqueness cages
(redundant — the inner grid supplies its own row/column distinctness once it
is a real `N x N` board), the fake corner givens marked solver-support, a
kropki clue that touches no border cell, and a border kropki block's own
`negative` list (not yet modeled on the ring). A border cell no clue
references is never created — the `outside-cells` layer
(`layers.outside_cells`) creates a cell only for an address some
constraint's own `cells` names.

`link_to_puzzle` runs this first and, on a frame, decodes the returned inner
document in place of the original and appends the border constraints
verbatim to the decoded puzzle — so the inner grid rides the same size,
domain, given, and uniqueness path every other classic/jigsaw link does, and
a border kropki dot rides the same `pair-difference`/`pair-ratio` layers an
ordinary interior dot does. One home per behavior: the peel adds no second
edge decode of its own — it calls `edge_clues.edge_to_pair` and the kropki
type's own builder (`edge_clues.KROPKI_PAIR_BUILDERS`), the same primitives
the ordinary (fully-interior) kropki decode uses, over the frame's own
padded width, then shifts the 1-indexed pair it gets back down to the padded
outside-cell addressing.

Numbered Rooms — a `type 1000` custom constraint named `Numbered Rooms` — is
decoded here too: each of its `input.groups` carries one group's raw cell
indices, head the outside cell and tail its row/column's line ordered from
the clue inward (`CustomIndexComponent`'s own shape), read against the
frame's own padded width exactly as a border kropki dot is, into one
`numbered-rooms` `Constraint` per group — `layers.numbered_rooms` reads it
back onto the shared element/indexing seam (ADR-0019). The rest of the
border clue vocabulary (XV, the cages) is still unmodeled and drops with the
ring's other scaffolding.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Any, cast

from gridfind.cell_geometry import format_address, parse_address
from gridfind.puzzle import Constraint
from gridfind.sudokumaker.addresses import index_to_address
from gridfind.sudokumaker.boundary import as_int
from gridfind.sudokumaker.dropped import constraint_name
from gridfind.sudokumaker.edge_clues import KROPKI_PAIR_BUILDERS, edge_to_pair
from gridfind.sudokumaker.naming import named_component
from gridfind.sudokumaker.wire_types import CUSTOM_CONSTRAINT_TYPE

_GIVENS_TYPE = 0
_REGIONS_TYPE = 1


def _enabled_raw_blocks(puzzle_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every enabled dict block of the raw, pre-bucket `constraints` list, in
    wire order — the one skip rule (not a dict, or `disabled` is `True`) the
    frame peel's own block walks share. Distinct from `boundary.enabled_blocks`:
    that one walks the post-bucket table `bucket_constraints_by_type` builds,
    which the peel runs before — the frame is recognised and rewritten off the
    raw document, ahead of any bucketing."""
    for block in puzzle_data.get("constraints", []):
        if isinstance(block, dict) and block.get("disabled") is not True:
            yield cast("dict[str, Any]", block)


def peel_escape_frame(
    document: dict[str, object],
) -> tuple[dict[str, object], tuple[Constraint, ...]] | None:
    """The inner `N x N` document of an escape-the-grid frame, paired with its
    decoded border-kropki `Constraint`s, or `None` when the link is not a
    frame.

    A frame is a square link whose declared domain is two digits short of its
    width — `width == height == maxDigit + 2` — with a border ring drawn outside
    the real regions. A classic or plain custom link never matches: its domain
    spans the full width. The returned document carries the inner cells, `size`
    `N` (so the domain reads back as `1..N`), and the peeled `type 1` region
    matrix; the original stays untouched.

    Every border-ring feature but a border-touching kropki dot drops here with
    a loud stderr warning — most of the ring is still unmodeled, so it fails
    loud rather than silently shrinking the ruleset the verdict runs under."""
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

    border_constraints = (
        *_border_kropki_constraints(puzzle_data, frame, inner),
        *_numbered_rooms_constraints(puzzle_data, frame, inner),
    )
    _warn_dropped_border(puzzle_data, frame, inner)
    inner_puzzle: dict[str, object] = {
        "cells": _peel_inner(cells, frame, inner),
        "size": inner,
        "constraints": inner_constraints,
    }
    return {**document, "puzzle": inner_puzzle}, border_constraints


def _padded_pair(edge: int, frame: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """`edge` decoded against the full `frame`x`frame` grid (`edge_to_pair`,
    the one home for the edge arithmetic) and shifted down to the padded
    outside-cell coordinate: the frame's own 1-indexed row/col minus one is
    exactly `0..N+1`, with `0`/`N+1` the border ring and `1..N` the inner
    grid's own addressing (CONTEXT.md, "outside cell")."""
    a, b = edge_to_pair(edge, frame)
    return _shift(a), _shift(b)


def _shift(address: str) -> tuple[int, int]:
    row, col = parse_address(address)
    return row - 1, col - 1


def _touches_border(position: tuple[int, int], inner: int) -> bool:
    """`True` when a padded `(row, col)` sits on the border ring (`0` or
    `inner + 1`), not inside the `1..inner` grid."""
    row, col = position
    return not (1 <= row <= inner and 1 <= col <= inner)


def _border_kropki_constraints(
    puzzle_data: dict[str, Any], frame: int, inner: int
) -> list[Constraint]:
    """Every `type 200`/`201` kropki clue whose decoded pair touches the
    border ring, as its canonical `pair-difference`/`pair-ratio` `Constraint`
    over the padded outside-cell addresses — built through
    `edge_clues.KROPKI_PAIR_BUILDERS`, the same type-to-relation dispatch the
    ordinary interior decode uses, so a border dot and an interior dot read
    one clue's `value` the same way. A clue whose pair lands entirely inside
    the `1..inner` grid is left for `_warn_dropped_kropki_remainder` to
    account for — it is not modeled here."""
    constraints: list[Constraint] = []
    for block in _enabled_raw_blocks(puzzle_data):
        builder = KROPKI_PAIR_BUILDERS.get(cast("object", block.get("type")))
        if builder is None:
            continue
        for clue in cast("list[dict[str, Any]]", block.get("clues", [])):
            position_a, position_b = _padded_pair(clue["edge"], frame)
            if _touches_border(position_a, inner) or _touches_border(position_b, inner):
                a, b = format_address(*position_a), format_address(*position_b)
                constraints.append(builder(clue["value"], a, b))
    return constraints


def _is_numbered_rooms_block(block: dict[str, Any]) -> bool:
    """True when `block` is a `type 1000` custom constraint whose declared
    `definition.name` (`dropped.constraint_name`) names the `Numbered Rooms`
    component — recognized through the one shared registry lookup
    (`naming.named_component`, the `"numbered-rooms"` role), the same seam
    `global_flags.has_somedoku_component` reads its own name by, never a
    second private name check."""
    if block.get("type") != CUSTOM_CONSTRAINT_TYPE:
        return False
    component = named_component(constraint_name(block))
    return component is not None and component.role == "numbered-rooms"


def _numbered_rooms_group_addresses(
    group: dict[str, Any], frame: int
) -> list[str] | None:
    """A Numbered Rooms group's raw `cells` (head the outside cell, tail its
    line ordered from the clue inward — `CustomIndexComponent`'s own shape)
    shifted down to the padded outside-cell addressing, or `None` when the
    group carries too few cells to name a relation at all."""
    raw_cells = group.get("cells")
    if not isinstance(raw_cells, list) or len(raw_cells) < 2:
        return None
    return [
        format_address(*_shift(index_to_address(cast("int", index), frame)))
        for index in raw_cells
    ]


def _numbered_rooms_constraints(
    puzzle_data: dict[str, Any], frame: int, inner: int
) -> list[Constraint]:
    """Every `Numbered Rooms` group whose head names an outside cell, as a
    `numbered-rooms` `Constraint` carrying `params["cells"] = [outside,
    *line]` — the shape `layers.numbered_rooms` reads back onto the shared
    element/indexing seam (ADR-0019). A group that decodes to too few cells,
    or whose head does not touch the border ring, carries no rule here;
    `_warn_dropped_numbered_rooms_remainder` accounts for it instead of
    silently modeling nothing."""
    constraints: list[Constraint] = []
    for block in _enabled_raw_blocks(puzzle_data):
        if not _is_numbered_rooms_block(block):
            continue
        payload = block.get("input")
        groups = payload.get("groups") if isinstance(payload, dict) else None
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            cells = _numbered_rooms_group_addresses(group, frame)
            if cells is None:
                continue
            if not _touches_border(parse_address(cells[0]), inner):
                continue
            constraints.append(Constraint("numbered-rooms", params={"cells": cells}))
    return constraints


def _warn_dropped_numbered_rooms_remainder(
    block: dict[str, Any], frame: int, inner: int
) -> None:
    """Warn to stderr for every group in a Numbered Rooms block
    `_numbered_rooms_constraints` did not decode: too few cells to name a
    relation, or a head that is not itself an outside address — the relation
    is defined head-outside, tail-inward, so a group failing that shape
    carries no rule gridfind can honour."""
    payload = block.get("input")
    groups = payload.get("groups") if isinstance(payload, dict) else None
    if not isinstance(groups, list):
        return
    dropped = 0
    for group in groups:
        if not isinstance(group, dict):
            dropped += 1
            continue
        cells = _numbered_rooms_group_addresses(group, frame)
        if cells is None or not _touches_border(parse_address(cells[0]), inner):
            dropped += 1
    if dropped:
        print(
            f"warning: escape-the-grid frame: dropping {dropped} Numbered "
            "Rooms group(s) whose shape gridfind cannot read as an "
            "outside-cell relation — verdict computed without them",
            file=sys.stderr,
        )


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
    for block in _enabled_raw_blocks(puzzle_data):
        if block.get("type") != _REGIONS_TYPE:
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
    """Warn to stderr for every border-ring feature still dropped: each
    enabled constraint block that is neither givens (`type 0`), the
    peeled regions (`type 1`), nor a kropki block (`type 200`/`201`, handled
    by `_warn_dropped_kropki_remainder` below) — the cosmetic outline, the
    postproc constraint, the Rows/Cols cages — and any border cell carrying a
    given. Silence is the one forbidden response: the ring is real data the
    verdict runs without, save the border kropki dots `peel_escape_frame`
    already forwarded.

    Louder than `dropped.has_live_data` for the blocks it does warn about —
    that predicate reads a cosmetic-only `type 2000` outline as inert, but
    here it too is dropped puzzle content, so it warns."""
    for block in _enabled_raw_blocks(puzzle_data):
        kind = block.get("type")
        if kind in (_GIVENS_TYPE, _REGIONS_TYPE):
            continue
        if kind in KROPKI_PAIR_BUILDERS:
            _warn_dropped_kropki_remainder(block, frame, inner)
            continue
        if _is_numbered_rooms_block(block):
            _warn_dropped_numbered_rooms_remainder(block, frame, inner)
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


def _warn_dropped_kropki_remainder(
    block: dict[str, Any], frame: int, inner: int
) -> None:
    """Warn to stderr for the part of a border kropki block
    `_border_kropki_constraints` did not forward: a clue whose pair never
    touches the border ring (the outside-cell machinery only models a clue
    that names an outside cell), and the block's own `negative` list (the
    negative-space mechanism is not modeled against the border ring)."""
    kind = block.get("type")
    non_border = sum(
        1
        for clue in cast("list[dict[str, Any]]", block.get("clues", []))
        if not any(
            _touches_border(position, inner)
            for position in _padded_pair(clue["edge"], frame)
        )
    )
    if non_border:
        print(
            f"warning: escape-the-grid frame: dropping {non_border} interior "
            f"kropki clue(s) (type {kind!r}) — none names an outside cell",
            file=sys.stderr,
        )
    negative = block.get("negative")
    if isinstance(negative, list) and negative:
        print(
            "warning: escape-the-grid frame: dropping a border kropki block's "
            f"negative-space rule (type {kind!r}) — not modeled on the ring",
            file=sys.stderr,
        )


def _is_border_index(index: int, frame: int, inner: int) -> bool:
    """True when a row-major frame index sits on the border ring (row/col `0` or
    `frame - 1`), not in the inner `1..N` band."""
    row, col = divmod(index, frame)
    return not (1 <= row <= inner and 1 <= col <= inner)
