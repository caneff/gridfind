"""Composition point for the layers package (issue #17).

Assembles the layer and preset registries from the per-layer modules as an
explicit list — no decorator, no import-side-effect auto-discovery — and holds
the stack-resolution API (`resolve`, `expand_stack`, `UnknownLayerError`) that
callers use today.

`gridfind.layers` is **internal-only** — no external or plugin callers (issues
#18, #24). Its committed public surface is exactly `__all__` below: the stack
API `verdict.py` consumes. Everything else here — the registries, and the
layer classes imported to build them — is implementation detail: used in-tree,
not part of the committed surface, and free to change. Tests reach the layer
classes through their own submodules (e.g. `gridfind.layers.regions`).

The engine->layer contract a layer author codes against (`Layer`, `add_cell`,
`register_structure`) is a separate surface, tracked in issue #26.
"""

from __future__ import annotations

from gridfind.engine import GridfindError, Layer
from gridfind.layers.board import Board
from gridfind.layers.cols import ColsDistinct
from gridfind.layers.line_count import LineCountDistinct
from gridfind.layers.regions import RegionsDistinct, _irregular_demo_region_map
from gridfind.layers.rows import RowsDistinct

__all__ = ["UnknownLayerError", "expand_stack", "resolve"]


class UnknownLayerError(GridfindError):
    """A stack names a layer the registry doesn't recognize."""


LAYER_REGISTRY = {
    "board": Board(),
    "rows-distinct": RowsDistinct(),
    "cols-distinct": ColsDistinct(),
    "regions-distinct": RegionsDistinct(),
    "regions-distinct-irregular": RegionsDistinct(
        name="regions-distinct-irregular",
        region_map=_irregular_demo_region_map(),
    ),
    "line-count-distinct": LineCountDistinct(),
}

PRESET_REGISTRY: dict[str, list[str]] = {
    "classic-sudoku": ["board", "rows-distinct", "cols-distinct", "regions-distinct"],
}


def expand_stack(stack: str | list[str]) -> list[str]:
    """Expand preset names in a stack spec into their layer lists (spec #4,
    decision 29; issue #9). A bare string is a single-entry stack. A name
    that is neither a registered preset nor a registered layer is rejected
    rather than silently passed through.
    """
    names = [stack] if isinstance(stack, str) else stack
    expanded: list[str] = []
    for name in names:
        if name in PRESET_REGISTRY:
            expanded.extend(expand_stack(PRESET_REGISTRY[name]))
        elif name in LAYER_REGISTRY:
            expanded.append(name)
        else:
            msg = f"unknown layer or preset {name!r}"
            raise UnknownLayerError(msg)
    return expanded


def resolve(stack: str | list[str]) -> list[Layer]:
    """Resolve a stack of layer/preset names to layer instances via the
    registries."""
    return [LAYER_REGISTRY[name] for name in expand_stack(stack)]
