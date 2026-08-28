"""Shared home for the digit-bitmask-group helpers a `groups` param feeds:
each entry a bitmask over the board's digits, bit `d` set meaning digit `d`
is a member. The grouped line (`layers/line.py`, `"grouped"` relation) is
the first caller; window-groups (#758) is the laid-out second import point,
so a fix to the partition check or the group-index table lands once for
both rather than drifting between two copies.
"""

from __future__ import annotations

from gridfind.engine import MalformedPuzzleError


def validate_partition(groups: list[int], board_values: range) -> None:
    """`groups` must partition the board's own digits — no digit left
    uncovered (a gap) and no digit claimed by two groups (an overlap).
    Takes `board_values` rather than reading `engine.board` itself: the
    board's digit domain is a puzzle-wide fact, not a per-wire-block one, so
    callers resolve it once and pass it in."""
    domain_mask = 0
    for value in board_values:
        domain_mask |= 1 << value
    union = 0
    overlap = 0
    for mask in groups:
        overlap |= union & mask
        union |= mask
    if union != domain_mask or overlap:
        msg = (
            f"groups {groups!r} do not partition the board's digits "
            f"{list(board_values)!r} — check for a gap or overlap"
        )
        raise MalformedPuzzleError(msg)


def group_index_table(groups: list[int], board_values: range) -> list[tuple[int, int]]:
    """Every `(digit, group_index)` pair `groups` names — digit `d` belongs
    to group index `g` when bit `d` of `groups[g]` is set. Feeds
    `add_allowed_assignments` for a per-cell group-index variable."""
    return [
        (value, group_index)
        for group_index, mask in enumerate(groups)
        for value in board_values
        if mask & (1 << value)
    ]
