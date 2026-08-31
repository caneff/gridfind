"""`DECODER_REGISTRY`: the one table wire-type -> (handler, live-data payload
keys, display name, toggle flag) that `link_to_puzzle` dispatches through,
`dropped.warn_on_dropped_constraints` treats as the already-modeled ruleset,
and `dropped.has_live_data` reads `live_keys`/`is_toggle` from. Also the
global-toggle types (anti-knight, anti-king, the two diagonals) and their
shared handler factory `_global_toggle_handler` — bare
enabled-presence-is-the-rule blocks that exist only to feed rows into this
registry, so they're defined alongside it rather than given their own module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.arrow import arrow_constraints
from gridfind.sudokumaker.boundary import ConstraintBuckets, enabled_blocks
from gridfind.sudokumaker.cages import cage_constraints, thermo_constraints
from gridfind.sudokumaker.clone import clone_constraints
from gridfind.sudokumaker.edge_clues import (
    black_kropki_constraints,
    kropki_constraints,
    xv_constraints,
)
from gridfind.sudokumaker.flat_cells import (
    col_indexing_constraints,
    even_constraints,
    extra_region_constraints,
    odd_constraints,
    row_indexing_constraints,
)
from gridfind.sudokumaker.line import (
    between_constraints,
    double_arrow_constraints,
    grouped_constraints,
    lockout_constraints,
    palindrome_constraints,
    region_sum_constraints,
    renban_constraints,
    sequence_constraints,
    whisper_constraints,
)
from gridfind.sudokumaker.quadruple import quadruple_constraints
from gridfind.sudokumaker.regions import regions_constraints
from gridfind.sudokumaker.wire_types import (
    ANTI_KING_TYPE,
    ANTI_KNIGHT_TYPE,
    ARROW_TYPE,
    BETWEEN_TYPE,
    CAGE_TYPE,
    CLONE_TYPE,
    COSMETIC_CAGE_TYPE,
    DISJOINT_GROUPS_TYPE,
    DOUBLE_ARROW_TYPE,
    EVEN_TYPE,
    EXTRA_REGION_TYPE,
    GIVENS_TYPE,
    GROUPED_TYPE,
    INDEXING_COL_TYPE,
    INDEXING_ROW_TYPE,
    KROPKI_BLACK_TYPE,
    KROPKI_WHITE_TYPE,
    LOCKOUT_TYPE,
    NEGATIVE_DIAGONAL_TYPE,
    NONCONSECUTIVE_TYPE,
    ODD_TYPE,
    PALINDROME_TYPE,
    POSITIVE_DIAGONAL_TYPE,
    QUADRUPLE_TYPE,
    REGION_SUM_TYPE,
    REGIONS_TYPE,
    RENBAN_TYPE,
    SEQUENCE_TYPE,
    THERMO_TYPE,
    WHISPER_TYPE,
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
    unmodeled types too), `name` labels it in the decoder's own warnings, and
    `is_toggle` marks a global toggle — a bare enabled block with no payload,
    whose presence alone is the rule — so `dropped.has_live_data` can derive
    its toggle set straight off this table instead of a hand-kept list that
    could drift from it.
    """

    handler: Callable[[ConstraintBuckets, int], list[Constraint]] | None
    live_keys: tuple[str, ...]
    name: str
    is_toggle: bool = False


DECODER_REGISTRY: dict[int, DecodedType] = {
    GIVENS_TYPE: DecodedType(handler=None, live_keys=(), name="givens"),
    REGIONS_TYPE: DecodedType(
        handler=regions_constraints, live_keys=(), name="regions"
    ),
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
    EXTRA_REGION_TYPE: DecodedType(
        handler=extra_region_constraints,
        live_keys=("cells",),
        name="extra-region",
    ),
    INDEXING_ROW_TYPE: DecodedType(
        handler=row_indexing_constraints,
        live_keys=("cells",),
        name="row-indexing",
    ),
    INDEXING_COL_TYPE: DecodedType(
        handler=col_indexing_constraints,
        live_keys=("cells",),
        name="col-indexing",
    ),
    EVEN_TYPE: DecodedType(
        handler=even_constraints,
        live_keys=("cells",),
        name="even",
    ),
    ODD_TYPE: DecodedType(
        handler=odd_constraints,
        live_keys=("cells",),
        name="odd",
    ),
    QUADRUPLE_TYPE: DecodedType(
        handler=quadruple_constraints,
        live_keys=("clues",),
        name="quadruple",
    ),
    CLONE_TYPE: DecodedType(
        handler=clone_constraints,
        live_keys=("groups",),
        name="clone",
    ),
    RENBAN_TYPE: DecodedType(
        handler=renban_constraints,
        live_keys=("lines",),
        name="renban",
    ),
    WHISPER_TYPE: DecodedType(
        handler=whisper_constraints,
        live_keys=("lines",),
        name="whisper",
    ),
    PALINDROME_TYPE: DecodedType(
        handler=palindrome_constraints,
        live_keys=("lines",),
        name="palindrome",
    ),
    BETWEEN_TYPE: DecodedType(
        handler=between_constraints,
        live_keys=("lines",),
        name="between",
    ),
    SEQUENCE_TYPE: DecodedType(
        handler=sequence_constraints,
        live_keys=("lines",),
        name="sequence",
    ),
    GROUPED_TYPE: DecodedType(
        handler=grouped_constraints,
        live_keys=("lines",),
        name="grouped",
    ),
    LOCKOUT_TYPE: DecodedType(
        handler=lockout_constraints,
        live_keys=("lines",),
        name="lockout",
    ),
    REGION_SUM_TYPE: DecodedType(
        handler=region_sum_constraints,
        live_keys=("lines",),
        name="region-sum",
    ),
    DOUBLE_ARROW_TYPE: DecodedType(
        handler=double_arrow_constraints,
        live_keys=("lines",),
        name="double-arrow",
    ),
    ARROW_TYPE: DecodedType(
        handler=arrow_constraints,
        live_keys=("bulbsWithArrows",),
        name="arrow",
    ),
    NEGATIVE_DIAGONAL_TYPE: DecodedType(
        handler=_global_toggle_handler(NEGATIVE_DIAGONAL_TYPE, "negative-diagonal"),
        live_keys=(),
        name="negative-diagonal",
        is_toggle=True,
    ),
    POSITIVE_DIAGONAL_TYPE: DecodedType(
        handler=_global_toggle_handler(POSITIVE_DIAGONAL_TYPE, "positive-diagonal"),
        live_keys=(),
        name="positive-diagonal",
        is_toggle=True,
    ),
    ANTI_KING_TYPE: DecodedType(
        handler=_global_toggle_handler(ANTI_KING_TYPE, "anti-king"),
        live_keys=(),
        name="anti-king",
        is_toggle=True,
    ),
    ANTI_KNIGHT_TYPE: DecodedType(
        handler=_global_toggle_handler(ANTI_KNIGHT_TYPE, "anti-knight"),
        live_keys=(),
        name="anti-knight",
        is_toggle=True,
    ),
    DISJOINT_GROUPS_TYPE: DecodedType(
        handler=_global_toggle_handler(DISJOINT_GROUPS_TYPE, "disjoint-groups"),
        live_keys=(),
        name="disjoint-groups",
        is_toggle=True,
    ),
    NONCONSECUTIVE_TYPE: DecodedType(
        handler=_global_toggle_handler(NONCONSECUTIVE_TYPE, "nonconsecutive"),
        live_keys=(),
        name="nonconsecutive",
        is_toggle=True,
    ),
}
