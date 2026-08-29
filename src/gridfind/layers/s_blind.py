"""The compose-time refusal of an `s_blind` layer over `schrodinger`.

An `s_blind` layer reads a cell through its single content slot, which has no
defined meaning once `schrodinger` widens every cell to two. `build_stack`
calls `refuse_s_blind_over_widening` to reject the pair up front and name the
offending layer, rather than let the s-blind layer read past a widened cell's
first slot alone deep in the solve.

`_S_BLIND_LAYER_TYPES` is empty: every layer declares a reading mode — value
or digit — and so composes with a widening layer on its own terms (ADR-0019
decision 5). The refusal therefore never fires, and the whole mechanism is
dead code; issue #523 tracks deleting it.
"""

from __future__ import annotations

from gridfind.engine import GridfindError, Layer

_S_BLIND_LAYER_TYPES: tuple[type, ...] = ()


class SBlindLayerError(GridfindError):
    """An `s_blind` layer — one that reads a cell's single content slot — is
    stacked with `schrodinger`, which widens cells to a second slot. The
    combination has no defined meaning, so `build_stack` refuses it rather
    than let the s-blind layer read past a widened cell's first slot alone."""


def refuse_s_blind_over_widening(layers: dict[str, Layer]) -> None:
    """Refuse a stack that pairs `schrodinger` with an `s_blind` layer.

    Names the first offending layer found, in stack order: its own
    constraint type is what a setter needs to see to fix their puzzle. With
    `_S_BLIND_LAYER_TYPES` empty, no stack offends and every call returns."""
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
