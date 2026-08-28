"""The `window-groups` layer: SudokuMaker's global entropy / global mod rule
(wire type 16) — every 2x2 window of the grid holds at least one
digit from each of the clue's own digit-bitmask groups. Entropic, modular,
and any other digit grouping a setter draws are this one rule, keyed only by
which groups the clue names, the same posture the grouped line's window rule
takes for the line-clue family (`layers/line.py`).

Digit mode, and window-structured like the grouped line: every grid cell
folds to its one real digit through `line.single_real_digits` before
windowing, so a Schrödinger-widened cell raises loud (via `sole`,
`engine.py`) rather than guess which slot the window would mean — the same
raise grouped-line and palindrome already stand up.

Unlike the grouped line's window (whose group count fixes the window's own
size and cycles the path), window-groups' window is always a fixed 2x2 block
of the grid, independent of the group count, and its rule is "at least one
member of each group present", not "exactly one member of each group, in a
bijection": a window may hold two digits of the same group, a digit
belonging to no group (a hand-edited gap), or a digit belonging to two
groups at once (a hand-edited overlap), and still satisfy every group's own
presence requirement. `bitmask_group.validate_group_masks` and
`group_membership_table` are this rule's own, laxer validation and table
shape — see that module's docstring for why the grouped line's
strict-partition `group_index_table` cannot represent a gap or an overlap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.cell_geometry import CellGeometry
from gridfind.engine import Engine
from gridfind.layers.bitmask_group import group_membership_table, validate_group_masks
from gridfind.layers.line import single_real_digits


def _windows(geometry: CellGeometry) -> list[list[str]]:
    """Every 2x2 window of the grid, row-major: `(size - 1) * (size - 1)`
    overlapping windows, each its own four addresses `[top-left, top-right,
    bottom-left, bottom-right]`."""
    grid = geometry.grid
    return [
        [
            grid[row][col],
            grid[row][col + 1],
            grid[row + 1][col],
            grid[row + 1][col + 1],
        ]
        for row in range(geometry.size - 1)
        for col in range(geometry.size - 1)
    ]


@dataclass
class WindowGroups:
    """Every enabled window-groups clue on the puzzle, each enforced on its
    own: a link naming both entropy and mod (two clues) enforces both, the
    per-type layer dedup (`layers/door.py`) folding them into this one
    shared instance rather than two.

    Per clue: `params["groups"]` names its own digit-bitmask groups. Each
    grid cell folds to its one real digit once (shared across every window
    and every clue); for each group, a per-cell "this cell's digit is a
    member" boolean is reified off that group's own membership table
    (`group_membership_table`); each window then requires at least one
    member-boolean true per group (`add_bool_or`)."""

    name: str = "window-groups"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        geometry = engine.cell_geometry
        addresses = [address for row in geometry.grid for address in row]
        digits = dict(
            zip(
                addresses,
                single_real_digits(
                    [engine.real_digit_slots(address) for address in addresses]
                ),
                strict=True,
            )
        )
        windows = _windows(geometry)
        for clue_index, clue in enumerate(engine.constraints_of(self.name)):
            groups = cast("list[int]", clue.params["groups"])
            validate_group_masks(groups, engine.board.values)
            membership: dict[tuple[str, int], cp_model.IntVar] = {}
            for group_index, mask in enumerate(groups):
                table = group_membership_table(mask, engine.board.values)
                for address in addresses:
                    member = engine.model.new_bool_var(
                        f"{self.name}.{clue_index}.{address}.group{group_index}"
                    )
                    engine.model.add_allowed_assignments(
                        [digits[address], member], table
                    )
                    membership[address, group_index] = member
            for window in windows:
                for group_index in range(len(groups)):
                    engine.model.add_bool_or(
                        [membership[address, group_index] for address in window]
                    )
