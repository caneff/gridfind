"""The three edge-clue types — XV (`type 202`), white-kropki (`type 200`),
black-kropki (`type 201`) — which share one wire shape (`clues: [{value,
edge}], negative: [...]`) and one decode walk (`_edge_clue_constraints`) built
on the shared edge-to-cell-pair primitive `edge_to_pair`.

All three edge-clue types' `negative` lists are enforced through the
negative-space mechanism (`_orthogonal_pairs`, `_negative_space_constraints`):
every orthogonally-adjacent pair a block's clues didn't mark is forbidden
each listed difference (white), ratio (black), or sum (XV).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from gridfind.cell_geometry import cell_geometry, format_address
from gridfind.layers.door import ALIAS_REGISTRY
from gridfind.puzzle import Board, Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, as_int, enabled_blocks
from gridfind.sudokumaker.wire_types import (
    KROPKI_BLACK_TYPE,
    KROPKI_WHITE_TYPE,
    XV_TYPE,
)

# The two forward 4-neighbour offsets (right, down) `_orthogonal_pairs` steps
# by. Stepping only these — never their mirrors (left, up) — is what keeps
# each unordered pair to one entry: the mirrored offset would just re-find
# the same neighbour from the other side.
_ORTHOGONAL_STEPS: tuple[tuple[int, int], ...] = ((0, 1), (1, 0))

# `value` selects the existing group-sum alias — 10 is X, 5 is V — never a
# raw `sum`, so a puzzle carrying both an XV clue and a literal group-sum on
# the same cells still hits the alias's own fixed-param conflict check in
# `expand_constraints`. Read off `gridfind.layers.door.ALIAS_REGISTRY` rather than
# restated here — the sum each alias fixes is stated once, in the registry
# that also builds it.
_XV_ALIASES: dict[int, str] = {
    cast("int", fixed["sum"]): alias
    for alias, (canonical, fixed) in ALIAS_REGISTRY.items()
    if canonical == "group-sum" and "sum" in fixed
}


def edge_to_pair(edge: int, size: int) -> tuple[str, str]:
    """An XV/kropki `edge` integer decoded to its two orthogonally-adjacent
    cell addresses, the primitive shared by the XV and white-kropki
    decoders — and, called against a frame's own padded width, by
    `sudokumaker.frame`'s border-kropki decode (the arithmetic is agnostic to
    what `size` means; `frame.py` shifts the 1-indexed pair it returns down
    to the padded outside-cell addressing itself).

    Edges are enumerated in row-major blocks of `2 * size`, one block per
    0-indexed row `r0`: within a block, offset `1..size-1` is a horizontal
    (left/right) pair starting `r0`, and offset `size..2*size-1` is a
    vertical (up/down) pair starting `r0` — the two closed-form formulas
    (`edge = 2N*r0 + c0 + 1` horizontal, `edge = 2N*r0 + c0 + N` vertical)
    inverted by `divmod`. Oracle-verified against a real link: X @ 70
    = R4C8/R5C8, V @ 103 = R6C5/R7C5 (vertical), kropki @ 75 = R5C3/R5C4, @
    132 = R8C6/R8C7 (horizontal), all on a 9x9 board.

    Raises `ValueError` when `edge` names no in-bounds pair on a `size`x`size`
    board (an out-of-range offset, or a row with no room for the pair)."""
    block = 2 * size
    r0, offset = divmod(edge, block)
    if 1 <= offset <= size - 1 and 0 <= r0 <= size - 1:
        c0 = offset - 1
        return format_address(r0 + 1, c0 + 1), format_address(r0 + 1, c0 + 2)
    if size <= offset <= block - 1 and 0 <= r0 <= size - 2:
        c0 = offset - size
        return format_address(r0 + 1, c0 + 1), format_address(r0 + 2, c0 + 1)
    msg = (
        f"non-classic link: edge {edge!r} does not name a valid cell pair "
        f"on a {size}x{size} board"
    )
    raise ValueError(msg)


def pair_to_edge(row: int, col: int, size: int) -> int:
    """The `edge` index of the horizontal pair starting at 1-based `(row,
    col)` and its right neighbor — `edge_to_pair`'s horizontal branch
    (`edge = 2*size*r0 + c0 + 1`) inverted for a caller that knows the pair
    and wants the wire's edge number, the shape every corpus synthesizer that
    labels a horizontal kropki/XV edge needs."""
    r0, c0 = row - 1, col - 1
    return 2 * size * r0 + c0 + 1


def _orthogonal_pairs(size: int) -> list[tuple[str, str]]:
    """Every orthogonally-adjacent cell pair on a `size`x`size` board, each
    emitted once: grid x the two forward 4-neighbour offsets x
    `CellGeometry.step`. Built locally rather than promoted to a shared
    `CellGeometry` enumerator — the negative-space mechanism below is its only
    consumer, and a shared primitive for one caller is speculative."""
    geometry = cell_geometry(Board(size=size))
    pairs: list[tuple[str, str]] = []
    for row in geometry.grid:
        for cell in row:
            for delta_row, delta_col in _ORTHOGONAL_STEPS:
                target = geometry.step(cell, delta_row, delta_col)
                if target is not None:
                    pairs.append((cell, target))
    return pairs


def _negative_space_constraints(
    size: int,
    marked: set[frozenset[str]],
    forbidden: list[object],
    build_negated_clue: Callable[[object, str, str], Constraint],
) -> list[Constraint]:
    """The negative-space mechanism: every orthogonally-adjacent pair on the
    board minus `marked` (the block's own positively-clued pairs, exempt
    because their dot already governs them), each value in `forbidden`
    applied over every one of those eligible pairs through
    `build_negated_clue` — the caller's own relation emitter in its negated
    mode, so a relation's positive and negative rule share one home and
    cannot drift apart."""
    eligible = [
        pair for pair in _orthogonal_pairs(size) if frozenset(pair) not in marked
    ]
    return [build_negated_clue(value, a, b) for value in forbidden for a, b in eligible]


def _negative_rule(
    size: int, build_negated: Callable[[object, str, str], Constraint]
) -> Callable[[dict[str, Any], set[frozenset[str]]], list[Constraint]]:
    """A `negative_rule` closure for `_edge_clue_constraints`: reads the
    block's `negative` list and, if non-empty, applies it through
    `_negative_space_constraints` with `build_negated` as the relation
    emitter. Shared by `kropki_constraints`, `black_kropki_constraints`, and
    `xv_constraints` so the negative-list handling has one home."""

    def rule(block: dict[str, Any], marked: set[frozenset[str]]) -> list[Constraint]:
        negative = block.get("negative")
        if not (isinstance(negative, list) and negative):
            return []
        return _negative_space_constraints(size, marked, negative, build_negated)

    return rule


def _edge_clue_constraints(
    buckets: ConstraintBuckets,
    size: int,
    type_: int,
    build_clue: Callable[[object, str, str], Constraint],
    negative_rule: Callable[[dict[str, Any], set[frozenset[str]]], list[Constraint]],
) -> list[Constraint]:
    """The shared decode walk behind the edge-clue types — XV, white-kropki,
    black-kropki — which share one wire shape (`clues: [{value, edge}],
    negative: [...]`). Every enabled `type_` block: each clue's `edge` decodes
    to its orthogonally-adjacent pair via `edge_to_pair`, then
    `build_clue(value, a, b)` turns the clue's raw `value` and that pair into
    one `Constraint`. A `disabled` block is skipped entirely. `build_clue`
    carries the single per-type variation — an alias lookup, a `diff`, a
    ratio `k`.

    `negative_rule`, called with the block and the set of pairs its own clues
    just marked, returns the constraints the negative-space mechanism
    (`_negative_space_constraints`) derives for a non-empty `negative` list —
    each caller's own opt-in into its negated relation (`_negative_rule`)."""
    decoded: list[Constraint] = []
    for block in enabled_blocks(buckets, type_):
        clues = cast("list[dict[str, Any]]", block.get("clues", []))
        marked: set[frozenset[str]] = set()
        for clue in clues:
            a, b = edge_to_pair(clue["edge"], size)
            decoded.append(build_clue(clue["value"], a, b))
            marked.add(frozenset((a, b)))
        decoded.extend(negative_rule(block, marked))
    return decoded


def xv_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 202` XV clues as aliased group-sum `Constraint`s: `value`
    selects the existing `x`/`v` alias (10/5), or the link is refused — no
    other value names an XV sum. See `_edge_clue_constraints` for the walk.

    A non-empty `negative` list is enforced, not dropped: each of its values
    is a forbidden sum, applied through the negative-space mechanism
    (`_negative_space_constraints`) over every orthogonally-adjacent pair the
    block's own clues didn't mark — `group-sum`'s negated mode (`sum !=
    s`), the same relation-emitter the positive clues above use (via the
    `x`/`v` alias)."""

    def build(value: object, a: str, b: str) -> Constraint:
        # The XV wire value is a JSON number; the cast satisfies the int-keyed
        # lookup, and a non-int value simply misses it and raises below.
        alias = _XV_ALIASES.get(cast("int", value))
        if alias is None:
            msg = (
                f"non-classic link: XV clue value {value!r} is neither X (10) nor V (5)"
            )
            raise ValueError(msg)
        return Constraint(alias, params={"cells": [a, b]})

    def build_negated(value: object, a: str, b: str) -> Constraint:
        return Constraint(
            "group-sum", params={"cells": [a, b], "sum": value, "negate": True}
        )

    return _edge_clue_constraints(
        buckets, size, XV_TYPE, build, _negative_rule(size, build_negated)
    )


def kropki_pair_constraint(value: object, a: str, b: str) -> Constraint:
    """A white-kropki clue's `value` (the target difference, honored
    verbatim — a labelled non-1 dot is never coerced to the consecutive
    default) and its decoded pair as a `pair-difference` `Constraint`. The
    positive-mode builder `kropki_constraints` applies over a `type 200`
    block's own edges; `sudokumaker.frame`'s border-kropki decode calls it
    directly over a pair it has already decoded against the frame's own
    padded width, so the two never drift onto two different readings of a
    white-kropki clue's `value`."""
    return Constraint("pair-difference", params={"cells": [a, b], "diff": value})


def black_kropki_pair_constraint(value: object, a: str, b: str) -> Constraint:
    """A black-kropki clue's `value` (the target integer ratio `k`, honored
    verbatim — a labelled non-2 dot is never coerced to 2; a non-integer
    `value` raises `ValueError` rather than modeling a wrong verdict) and its
    decoded pair as a `pair-ratio` `Constraint`. Mirrors
    `kropki_pair_constraint`'s dual role for black kropki: the positive-mode
    builder here and `sudokumaker.frame`'s border-kropki decode both call it,
    so a black dot reads one way everywhere."""
    k = as_int(value, "black-kropki value")
    return Constraint("pair-ratio", params={"cells": [a, b], "k": k})


# The two kropki wire types' positive-mode builders, keyed by wire `type` —
# `sudokumaker.frame`'s border-kropki decode reads this rather than
# reimplementing the type-to-relation dispatch `_edge_clue_constraints`
# already makes for the ordinary (fully-interior) decode below.
KROPKI_PAIR_BUILDERS: dict[int, Callable[[object, str, str], Constraint]] = {
    KROPKI_WHITE_TYPE: kropki_pair_constraint,
    KROPKI_BLACK_TYPE: black_kropki_pair_constraint,
}


def kropki_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 200` white-kropki clues as `pair-difference` `Constraint`s
    via `kropki_pair_constraint`. `type 201` (black/ratio) has its own
    handler. See `_edge_clue_constraints` for the walk.

    A non-empty `negative` list is enforced, not dropped: each of its values
    is a forbidden difference, applied through the negative-space mechanism
    (`_negative_space_constraints`) over every orthogonally-adjacent pair the
    block's own clues didn't mark — `differs_by`'s negated mode
    (`pair-difference` with `negate: true`), the same relation-emitter the
    positive clues above use. The wire's own `overrideNegativeDifferences`
    boolean is a known-inert field (never exposed in SudokuMaker, carries no
    puzzle meaning) and is never read here."""

    def build_negated(value: object, a: str, b: str) -> Constraint:
        return Constraint(
            "pair-difference", params={"cells": [a, b], "diff": value, "negate": True}
        )

    return _edge_clue_constraints(
        buckets,
        size,
        KROPKI_WHITE_TYPE,
        kropki_pair_constraint,
        _negative_rule(size, build_negated),
    )


def black_kropki_constraints(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
    """The `type 201` black-kropki clues as `pair-ratio` `Constraint`s via
    `black_kropki_pair_constraint`. See `_edge_clue_constraints` for the walk.

    A non-empty `negative` list is enforced, not dropped: each of its values
    is a forbidden ratio, applied through the negative-space mechanism
    (`_negative_space_constraints`) over every orthogonally-adjacent pair the
    block's own clues didn't mark — `ratio_of`'s negated mode (`pair-ratio`
    with `negate: true`), the same relation-emitter the positive clues above
    use. The wire's own `overrideNegativeRatios` boolean is a known-inert
    field (never exposed in SudokuMaker, carries no puzzle meaning) and is
    never read here."""

    def build_negated(value: object, a: str, b: str) -> Constraint:
        k = as_int(value, "black-kropki negative value")
        return Constraint(
            "pair-ratio", params={"cells": [a, b], "k": k, "negate": True}
        )

    return _edge_clue_constraints(
        buckets,
        size,
        KROPKI_BLACK_TYPE,
        black_kropki_pair_constraint,
        _negative_rule(size, build_negated),
    )
