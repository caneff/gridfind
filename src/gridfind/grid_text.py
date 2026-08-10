"""GridText: the bordered text format shared by `Witness.render()`
(`witness.py`) and `witness_validator`'s parser (issue #210).

Before this module, the shape — "N+1 border lines interleave with N cell
lines, one token per cell, starting and ending on a border line" — lived
twice: once as `Witness.render()`'s loop structure, once as
`witness_validator._parse_grid`'s re-derivation of the same layout. Nothing
named the two as one contract, so a layout change to `render()` could drift
out from under the validator's assumptions with no test to catch it. This
module is that contract's one home: both sides cite it instead of each
re-deriving it.

Neither renderer nor validator import each other (spec #185) — the
validator must never grade the renderer's homework using the renderer's own
code. This module is a spec the two sides share, not an implementation
either owns; it has no opinion on *why* a grid looks the way it does, only
on the token/line shape both must agree on.

A cell prints as a bare digit (`"5"`) for a singleton, or a curly pair
(`"{0 5}"`, unordered) for a Schrödinger S-cell (issue #141, decision #135).
The whole grid is `line_count(size)` text lines: a border line (junctions
and edges, no cell tokens), then a cell line, alternating, starting and
ending on a border line.
"""

from __future__ import annotations

import re

CELL_PATTERN = re.compile(r"\{(\d+) (\d+)\}|(\d+)")


def format_cell(content: tuple[int, ...]) -> str:
    """A cell's assignment tuple as a GridText token: a bare digit for a
    singleton, `{a b}` for a Schrödinger S-cell's unordered pair (issue
    #141, decision #135)."""
    if len(content) == 1:
        return str(content[0])
    a, b = content
    return f"{{{a} {b}}}"


def parse_cell(match: re.Match[str]) -> tuple[int, ...]:
    """The inverse of `format_cell`: a `CELL_PATTERN` match back to a cell
    tuple."""
    pair_a, pair_b, single = match.groups()
    if single is None:
        return (int(pair_a), int(pair_b))
    return (int(single),)


def line_count(size: int) -> int:
    """How many text lines a `size`x`size` GridText grid holds: `size + 1`
    border lines interleaved with `size` cell lines (issue #124's render
    shape)."""
    return 2 * size + 1


def cell_line_indices(size: int) -> range:
    """Which of `line_count(size)` lines hold cell tokens rather than a
    border — every other line, starting at index 1."""
    return range(1, line_count(size), 2)
