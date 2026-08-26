"""The compose-time refusal of an `s_blind` layer over `schrodinger`.

`NumberedRooms` reads a cell through its single content slot, which has no
defined meaning once `schrodinger` widens every cell to two. `build_stack`
calls `refuse_s_blind_over_widening` to reject the pair up front and name
the offending layer, rather than let the s-blind layer read past a widened
cell's first slot alone deep in the solve. Issue #523 tracks retiring the
`s_blind` flag itself once a widening-aware read exists for this last
holdout too (ADR-0019 dec 5); this direct check names the one remaining
concrete layer rather than scanning the stack for the property.
"""

from __future__ import annotations

from gridfind.engine import GridfindError, Layer
from gridfind.layers.numbered_rooms import NumberedRooms

_S_BLIND_LAYER_TYPES: tuple[type, ...] = (NumberedRooms,)


class SBlindLayerError(GridfindError):
    """An `s_blind` layer — one that reads a cell's single content slot — is
    stacked with `schrodinger`, which widens cells to a second slot. The
    combination has no defined meaning, so `build_stack` refuses it rather
    than let the s-blind layer read past a widened cell's first slot alone."""


def refuse_s_blind_over_widening(layers: dict[str, Layer]) -> None:
    """Refuse a stack that pairs `schrodinger` with an `OffsetAdjacency` or
    `NumberedRooms` layer.

    Names the first offending layer found, in stack order: its own
    constraint type is what a setter needs to see to fix their puzzle."""
    if "schrodinger" not in layers:
        return
    blind_name = next(
        (
            name
            for name, layer in layers.items()
            if isinstance(layer, _S_BLIND_LAYER_TYPES)
        ),
        None,
    )
    if blind_name is None:
        return
    msg = (
        f"{blind_name!r} reads a cell's single content slot; it has no "
        "defined meaning next to 'schrodinger', which widens every cell to "
        "two"
    )
    raise SBlindLayerError(msg)
