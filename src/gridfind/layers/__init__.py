"""Composition point for the layers package.

`gridfind.layers` is **internal-only** — no external or plugin callers. Its
committed public surface is exactly `__all__` below: `build_stack`, the
constraint dispatch API `verdict.py` consumes. The door itself —
`build_stack`, `expand_constraints`, `UnknownLayerError`, and the
layer/preset/alias registries — lives in `layers/door.py`; the
compose-time refusal of `OffsetAdjacency`/`NumberedRooms` over `schrodinger`
and its `SBlindLayerError` live in `layers/s_blind.py`. Everything beyond
`__all__` is implementation detail:
used in-tree, not part of the committed surface, and free to change. Tests
reach the layer classes and the two error types through their own
submodules (e.g. `gridfind.layers.regions`, `gridfind.layers.door`,
`gridfind.layers.s_blind`).

The engine->layer contract a layer author codes against (`Layer`, `add_cell`,
`register_structure`) is a separate surface.
"""

from __future__ import annotations

from gridfind.layers.door import build_stack

__all__ = [
    "build_stack",
]
