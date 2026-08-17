"""`DECODER_REGISTRY`: the one table wire-type -> (handler, live-data payload
keys, display name) that `link_to_puzzle` dispatches through,
`dropped.warn_on_dropped_constraints` treats as the already-modeled ruleset,
and `dropped.has_live_data` reads `live_keys` from. Also the global-toggle
types (anti-knight, anti-king, the two diagonals) and their shared handler
factory `_global_toggle_handler` — bare enabled-presence-is-the-rule blocks
that exist only to feed rows into this registry, so they're defined alongside
it rather than given their own module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.cages import cage_constraints, thermo_constraints
from gridfind.sudokumaker.edge_clues import (
    black_kropki_constraints,
    kropki_constraints,
    xv_constraints,
)
from gridfind.sudokumaker.regions import regions_constraints
from gridfind.sudokumaker.wire_types import (
    ANTI_KING_TYPE,
    ANTI_KNIGHT_TYPE,
    CAGE_TYPE,
    COSMETIC_CAGE_TYPE,
    KROPKI_BLACK_TYPE,
    KROPKI_WHITE_TYPE,
    NEGATIVE_DIAGONAL_TYPE,
    POSITIVE_DIAGONAL_TYPE,
    THERMO_TYPE,
    XV_TYPE,
)


def _global_toggle_handler(
    wire_type: int, constraint_type: str
) -> Callable[[ConstraintBuckets, int], list[Constraint]]:
    """A decoder for a bare global-toggle block (anti-knight, anti-king, a
    single diagonal): the block carries no payload — its enabled presence is
    the whole rule — so any enabled block of `wire_type` stands up
    `constraint_type` once, and a cosmetic `style` on the block is ignored. A
    `disabled` block contributes nothing (the setter switched the rule off)."""

    def handler(buckets: ConstraintBuckets, size: int) -> list[Constraint]:
        for _ in enabled_blocks(buckets, wire_type):
            return [Constraint(constraint_type)]
        return []

    return handler


@dataclass(frozen=True)
class DecodedType:
    """One SudokuMaker wire-type the decoder recognizes, one row wide: `handler` builds
    this type's `Constraint`s from the link (`None` for a type with nothing to
    build through `link_to_puzzle`'s generic dispatch — a bare `type 0` is just
    the unconditional rows/cols, and `type 2001` cosmetic cages are dispatched
    by hand for their richer `_CosmeticCageDecode` return; `type 1`'s regions
    live behind
    `regions_constraints` like every other generically-dispatched handler),
    `live_keys` are the payload keys that mark this type's wire shape as
    carrying a real rule (read by `dropped.has_live_data`, generalized to
    unmodeled types too), and `name` labels it in the decoder's own warnings.
    """

    handler: Callable[[ConstraintBuckets, int], list[Constraint]] | None
    live_keys: tuple[str, ...]
    name: str


DECODER_REGISTRY: dict[int, DecodedType] = {
    0: DecodedType(handler=None, live_keys=(), name="givens"),
    1: DecodedType(handler=regions_constraints, live_keys=(), name="regions"),
    KROPKI_WHITE_TYPE: DecodedType(
        handler=kropki_constraints,
        live_keys=("clues", "negative"),
        name="white-kropki",
    ),
    KROPKI_BLACK_TYPE: DecodedType(
        handler=black_kropki_constraints,
        live_keys=("clues", "negative"),
        name="black-kropki",
    ),
    XV_TYPE: DecodedType(
        handler=xv_constraints,
        live_keys=("clues", "negative"),
        name="XV",
    ),
    CAGE_TYPE: DecodedType(
        handler=cage_constraints,
        live_keys=("cages",),
        name="killer-cage",
    ),
    COSMETIC_CAGE_TYPE: DecodedType(
        handler=None,
        live_keys=("cages",),
        name="cosmetic-cage",
    ),
    THERMO_TYPE: DecodedType(
        handler=thermo_constraints,
        live_keys=("thermometers",),
        name="thermo",
    ),
    NEGATIVE_DIAGONAL_TYPE: DecodedType(
        handler=_global_toggle_handler(NEGATIVE_DIAGONAL_TYPE, "negative-diagonal"),
        live_keys=(),
        name="negative-diagonal",
    ),
    POSITIVE_DIAGONAL_TYPE: DecodedType(
        handler=_global_toggle_handler(POSITIVE_DIAGONAL_TYPE, "positive-diagonal"),
        live_keys=(),
        name="positive-diagonal",
    ),
    ANTI_KING_TYPE: DecodedType(
        handler=_global_toggle_handler(ANTI_KING_TYPE, "anti-king"),
        live_keys=(),
        name="anti-king",
    ),
    ANTI_KNIGHT_TYPE: DecodedType(
        handler=_global_toggle_handler(ANTI_KNIGHT_TYPE, "anti-knight"),
        live_keys=(),
        name="anti-knight",
    ),
}
