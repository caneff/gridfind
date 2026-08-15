"""The compose-time refusal of an `s_blind` layer over a widening layer.

A layer that reads a cell's single content slot declares `s_blind = True`; a
layer that widens cells to a second slot declares `widens = True` (`schrodinger`
today). The two have no defined meaning together, so `build_stack` calls
`refuse_s_blind_over_widening` to reject the pair up front and name the
offending layer, rather than let the s-blind layer read past a widened cell's
first slot alone deep in the solve.
"""

from __future__ import annotations

from gridfind.engine import GridfindError, Layer


class SBlindLayerError(GridfindError):
    """An `s_blind` layer — one that reads a cell's single content slot — is
    stacked with a layer that widens cells to a second slot (`schrodinger`
    today, any future widening layer as well). The combination has no
    defined meaning, so `build_stack` refuses it rather than let the s-blind
    layer read past a widened cell's first slot alone."""


def refuse_s_blind_over_widening(layers: dict[str, Layer]) -> None:
    """Refuse a stack that pairs an `s_blind` layer with a `widens` layer —
    keyed on those properties, not on the literal name `schrodinger`, so a
    future widening layer is covered for free.

    Names the first offending pair found, in stack order: the s-blind
    layer's own constraint type is the one a setter needs to see to fix
    their puzzle."""
    widening_name = next(
        (name for name, layer in layers.items() if getattr(layer, "widens", False)),
        None,
    )
    if widening_name is None:
        return
    blind_name = next(
        (name for name, layer in layers.items() if getattr(layer, "s_blind", False)),
        None,
    )
    if blind_name is None:
        return
    msg = (
        f"{blind_name!r} reads a cell's single content slot; it has no "
        f"defined meaning next to {widening_name!r}, which widens every "
        "cell to two"
    )
    raise SBlindLayerError(msg)
