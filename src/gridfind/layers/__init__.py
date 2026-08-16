"""Composition point for the layers package.

`gridfind.layers` is **internal-only** — no external or plugin callers. Its committed
public surface is exactly `__all__` below: the constraint
dispatch API `verdict.py` consumes (`build_stack`, `UnknownLayerError`,
`SBlindLayerError`). The door itself — `build_stack`, `expand_constraints`,
`UnknownLayerError`, and the layer/preset/alias registries — lives in
`layers/door.py`. Everything beyond `__all__` is implementation detail: used
in-tree, not part of the committed surface, and free to change. Tests reach
the layer classes through their own submodules (e.g. `gridfind.layers.regions`).

The engine->layer contract a layer author codes against (`Layer`, `add_cell`,
`register_structure`) is a separate surface.
"""

from __future__ import annotations

from gridfind.layers.door import UnknownLayerError, build_stack
from gridfind.layers.s_blind import SBlindLayerError

__all__ = [
    "SBlindLayerError",
    "UnknownLayerError",
    "build_stack",
]
