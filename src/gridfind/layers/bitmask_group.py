"""Shared home for the digit-bitmask-group helpers a `groups` param feeds:
each entry a bitmask over the board's digits, bit `d` set meaning digit `d`
is a member. The grouped line (`layers/line.py`, `"grouped"` relation) and
window-groups (`layers/window_groups.py`) both import from here rather than
each hand-rolling its own copy.

The two rules read `groups` differently, and so does their validation and
their table shape. The grouped line's `groups` must strictly partition the
board (`validate_partition`): its window-cycle rule pins one shared
`digit -> group_index` variable per cell (`group_index_table`), a shape that
only means something when every digit belongs to exactly one group. Window-
groups' `groups` may carry a gap or an overlap (`validate_group_masks`, the
laxer check): its "at least one cell per group present in the window" rule
reads each group as its own independent boolean per cell
(`group_membership_table`) — a digit outside every group simply never lights
any group's boolean, rather than leaving a cell with no legal group to land
in the way a gap would under the shared-index shape.
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


def validate_group_masks(groups: list[int], board_values: range) -> None:
    """Window-groups' own, laxer validation (spec #754): `groups` must be
    non-empty, and each mask must be non-zero and confined to the board's own
    digit domain. Unlike `validate_partition`, a gap (a digit in no group) or
    an overlap (a digit in two groups) is fine — the per-window "at least one
    cell from every named group" rule needs no exact partition to mean
    something. An empty `groups` list is refused outright: an unfilled global-
    entropy block (SudokuMaker's own "no size preset, groups added by hand"
    manual-config gap) states no rule to check."""
    if not groups:
        msg = "window-groups needs at least one group; groups is empty"
        raise MalformedPuzzleError(msg)
    domain_mask = 0
    for value in board_values:
        domain_mask |= 1 << value
    for index, mask in enumerate(groups):
        if mask == 0:
            msg = f"window-groups group {index} names no digits (mask 0)"
            raise MalformedPuzzleError(msg)
        if mask & ~domain_mask:
            msg = (
                f"window-groups group {index} (mask {mask:#x}) names a digit "
                f"outside the board's domain {list(board_values)!r}"
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


def group_membership_table(mask: int, board_values: range) -> list[tuple[int, int]]:
    """Every `(digit, 1-or-0)` pair over the board's own domain for one
    group's `mask`: `1` when bit `digit` of `mask` is set, else `0`. Feeds
    `add_allowed_assignments` for a per-cell, per-group reified "this cell's
    digit is a member of this group" boolean — window-groups' independent
    read of each group, which (unlike `group_index_table`'s single shared
    index) covers every digit in the board's domain regardless of gaps or
    overlaps between groups, since each group's table is built and enforced
    on its own."""
    return [(value, 1 if mask & (1 << value) else 0) for value in board_values]
