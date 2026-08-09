"""The one seam: verdict(puzzle, working_state=EMPTY) -> found | broke | unknown.

Races a broke-proof against a witness-find by handing CP-SAT's portfolio
solver a pure-satisfaction model — whichever is decidable first is what the
single `solve` call returns (spec #4, decisions 15, 15a, 32).

The input is the structured `Puzzle` + `WorkingState` (spec #45, issue #48):
the puzzle's constraints resolve to layers (issue #47), its board supplies
the grid, and givens/placements/candidates fix the model. Each call rebuilds the
engine from scratch — the build is ~1% of a solve, and no caller races many
working states over one puzzle, so no build-once/race-many API is offered
(ADR-0002).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine, MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.regions import (
    BOX_SHAPE,
    RegionMap,
    box_regions,
    region_map_from_labels,
)
from gridfind.puzzle import (
    EMPTY,
    BareSCell,
    BareSingleton,
    Candidate,
    Constraint,
    Given,
    HalfSCell,
    Placement,
    Puzzle,
    SDirective,
    SingletonPin,
    WorkingState,
)

VerdictKind = Literal["found", "broke", "unknown"]

DEFAULT_TIME_LIMIT_S = 10.0
DEFAULT_NUM_WORKERS = 8

# A box-drawing glyph for a grid junction, keyed by which arms (up, down,
# left, right) meet there. An arm is present where the region changes across
# it or at the outer edge (issue #124), so the glyph shows exactly the lines
# that meet — never a floating stub.
_JUNCTIONS = {
    (False, False, False, False): " ",
    (False, False, True, True): "─",
    (True, True, False, False): "│",
    (False, True, False, True): "┌",
    (False, True, True, False): "┐",
    (True, False, False, True): "└",
    (True, False, True, False): "┘",
    (True, True, False, True): "├",
    (True, True, True, False): "┤",
    (False, True, True, True): "┬",
    (True, False, True, True): "┴",
    (True, True, True, True): "┼",
}


@dataclass(frozen=True)
class Witness:
    """A found solve's content sequence per cell, paired with the board shape
    that read them (issue #72, pluralized #141) — self-describing, so a
    consumer lays the grid out without re-deriving addressing. `assignment`
    stays reachable directly for a caller that wants one cell, not a render.

    It is an *assignment*, not `values`: `Board.values` is the digit domain a
    cell may hold, and one word for both the offer and the choice reads badly
    three lines apart.

    A cell's tuple is a 1-tuple for a singleton, a 2-tuple `(a, b)`, `a < b`,
    for a Schrödinger S-cell (issue #141, spec #139's `schrodinger` layer,
    #133's content seam) — never the sentinel `contents()`/`values()` may
    also carry for an unsolved S-cell slot.

    `region_map` is the partition `render` borders against (issue #124) —
    always populated, never `None`: a board with no regions-distinct rule of
    its own still gets one region covering the whole board, so there is
    nothing to guess at render time."""

    grid: list[list[str]]
    assignment: dict[str, tuple[int, ...]]
    region_map: RegionMap

    def __getitem__(self, address: str) -> tuple[int, ...]:
        return self.assignment[address]

    def __len__(self) -> int:
        return len(self.assignment)

    def render(self) -> str:
        """The witness as text, bordered wherever two adjacent cells fall in
        different regions (issue #124): junctions are resolved from the four
        lines meeting at each grid node, so a classic box partition draws the
        familiar 3x3 boxes and a jigsaw partition draws its own region
        borders through the same path.

        A singleton cell prints its bare digit; an S-cell prints its
        unordered pair `{a b}` (issue #141, decision #135). Every cell is
        right-padded to the widest cell in the witness so columns stay
        aligned and the box banding survives whatever width an S-cell adds —
        for an ordinary witness (every cell a singleton) the widest cell is
        one character, so this is the same output as before.
        """
        n = len(self.grid)
        region_id = {
            cell: index for index, group in enumerate(self.region_map) for cell in group
        }

        def region_at(row: int, col: int) -> int:
            return region_id[(row + 1, col + 1)]

        def wall(row: int, col: int) -> bool:
            return (
                col == 0 or col == n or region_at(row, col - 1) != region_at(row, col)
            )

        def seg(row: int, col: int) -> bool:
            return (
                row == 0 or row == n or region_at(row - 1, col) != region_at(row, col)
            )

        def fmt(content: tuple[int, ...]) -> str:
            if len(content) == 1:
                return str(content[0])
            a, b = content
            return f"{{{a} {b}}}"

        formatted = [
            [fmt(self.assignment[address]) for address in row] for row in self.grid
        ]
        width = max(len(cell) for row in formatted for cell in row)

        lines: list[str] = []
        for b in range(n + 1):
            border = ""
            for c in range(n + 1):
                arms = (
                    b > 0 and wall(b - 1, c),
                    b < n and wall(b, c),
                    c > 0 and seg(b, c - 1),
                    c < n and seg(b, c),
                )
                border += _JUNCTIONS[arms]
                if c < n:
                    border += ("─" if seg(b, c) else " ") * (width + 2)
            lines.append(border)
            if b < n:
                cells = "".join(
                    ("│" if wall(b, c) else " ") + f" {formatted[b][c].rjust(width)} "
                    for c in range(n)
                )
                lines.append(cells + ("│" if wall(b, n) else " "))
        return "\n".join(lines)


@dataclass(frozen=True)
class Verdict:
    """`reason` is the broke witness's one explanation (issue #126, extended
    #158): set when a region in the resolved partition falls outside the
    cover feasibility band — outgrows the digit domain (`cells > domain`) or
    is too small to cover it even with Schrodinger S-cells (`domain >
    2*cells`) — either a fact that alone proves no completion exists. `None`
    on every other broke (an ordinary contradiction has no region to blame)
    and on found/unknown alike."""

    kind: VerdictKind
    witness: Witness | None = None
    reason: str | None = None


def verdict(
    puzzle: Puzzle,
    working_state: WorkingState = EMPTY,
    *,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    num_workers: int = DEFAULT_NUM_WORKERS,
) -> Verdict:
    # board is not a constraint — the puzzle's board supplies the grid. The
    # door expands presets and aliases exactly once and hands back both the
    # canonical constraints (so a layer's constraints_of(name) matches the
    # canonical types dispatch resolved on — an `x`/`v` clue reaches its
    # `pair-sum` layer as a sum-10/5 constraint) and the stack, compulsory
    # `board` layer already in it (issue #101).
    canonical, layers = build_stack(puzzle.constraints, size=puzzle.board.size)
    engine = build_engine(layers, tuple(canonical), board=puzzle.board)
    _apply(engine, puzzle.givens, working_state.places, working_state.candidates)
    _apply_s_directives(engine, working_state.s_directives)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = num_workers
    status = solver.solve(engine.model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        is_s = cast("dict[str, cp_model.IntVar] | None", engine.structures.get("is_s"))
        assignment: dict[str, tuple[int, ...]] = {}
        for address in engine.cells:
            content = engine.values(solver, address)
            is_this_s = is_s is not None and bool(solver.value(is_s[address]))
            assignment[address] = content if is_this_s else content[:1]
        grid = cast("list[list[str]]", engine.structures["grid"])
        region_map = _resolve_region_map(canonical, puzzle.board.size)
        witness = Witness(grid=grid, assignment=assignment, region_map=region_map)
        return Verdict(kind="found", witness=witness)
    if status == cp_model.INFEASIBLE:
        return Verdict(kind="broke", reason=_region_reason(canonical, puzzle))
    return Verdict(kind="unknown")


def _resolve_region_map(canonical: list[Constraint], size: int) -> RegionMap:
    """The region map the witness renders against: a setter-supplied jigsaw
    partition (issue #123's `params["regions"]`) when the puzzle's
    regions-distinct constraint carries one, the board's box tiling by
    convention otherwise, and — for a size with no box convention — one
    whole-board region, since no regions-distinct rule is being enforced for
    render to fail on."""
    for constraint in canonical:
        if constraint.type == "regions-distinct" and "regions" in constraint.params:
            return region_map_from_labels(size, constraint.params["regions"])
    if size in BOX_SHAPE:
        return box_regions(size, *BOX_SHAPE[size])
    return [[(row, col) for row in range(1, size + 1) for col in range(1, size + 1)]]


def _region_reason(canonical: list[Constraint], puzzle: Puzzle) -> str | None:
    """The broke witness's region-blame: the first region in the resolved
    partition outside the feasibility band `cells <= domain <= 2*cells`
    (spec #156 decision #151), named by its 1-based position and cell count
    against the domain size. Two symmetric violations:

    - **Over-sized** (`cells > domain`, issue #126): a forced repeat by
      pigeonhole. Holds regardless of Schrodinger widening — a region's
      `d0` slots alone already outnumber the domain.
    - **Under-coverable** (`domain > 2*cells`, issue #158): too few slots
      to cover the domain even with every cell doubled up as an S-cell.
      Only a real cause of infeasibility when `schrodinger` is in play — a
      region with no cover pressure just forbids repeats, and `domain >
      2*cells` alone never breaks that.

    Only checked when a regions-distinct constraint is actually in play, so
    a puzzle with no such rule (or an ordinary contradiction with every
    region in bounds) carries no message."""
    if not any(constraint.type == "regions-distinct" for constraint in canonical):
        return None
    region_map = _resolve_region_map(canonical, puzzle.board.size)
    domain_size = len(puzzle.board.values)
    has_schrodinger = any(constraint.type == "schrodinger" for constraint in canonical)
    for index, region in enumerate(region_map, start=1):
        cells = len(region)
        if cells > domain_size:
            return f"region {index} holds {cells} cells, domain is {domain_size}"
        if has_schrodinger and domain_size > 2 * cells:
            return (
                f"region {index} holds {cells} cells, domain is {domain_size} "
                "— too few to cover"
            )
    return None


def _apply(
    engine: Engine,
    givens: tuple[Given, ...],
    places: tuple[Placement, ...],
    candidates: tuple[Candidate, ...],
) -> None:
    """Fix the model from the structured givens and marks. A given and a
    placement both fix one digit; a candidate restricts a cell to a digit
    subset — all three go through the engine's one `restrict` call (issue
    #72). *Pin* is the Schrödinger layer's word, for the S-cell axis; a plain
    digit fix borrows nothing from it."""
    for fixed in (*givens, *places):
        engine.restrict(fixed.address, {fixed.digit})
    for candidate in candidates:
        engine.restrict(candidate.address, candidate.digits)


def _apply_s_directives(engine: Engine, directives: tuple[SDirective, ...]) -> None:
    """Apply the Schrödinger directives by restricting the already-built model
    along the two axes `engine.restrict` can't reach: S-cell-ness (`is_s`) and
    the second content slot (`d1`). Each names a point on those axes (#142):

    - singleton pin  — fix d0 to the digit, force is_s false.
    - S-cell pin     — fix both slots to the sorted pair, force is_s true.
    - bare singleton — force is_s false, digit free.
    - bare S-cell    — force is_s true, digits free.
    - half S-cell    — force is_s true and the digit into *either* slot, its
                       partner free (`digit in content`, an OR over the slots'
                       reified holds, which `engine.reify_holds` builds).

    A consistent directive narrows the model and is honored; a contradictory
    one makes it infeasible, which the solver reports as broke.

    Two content errors are malformed, refused here before the solve (#142):
    a directive naming a digit off the board (singleton/half/S-cell pin), and
    *any* directive on a stack with no schrodinger layer to honor it. The
    missing-layer check runs first, so a directive with a legal digit still
    refuses when the layer is absent."""
    if not directives:
        return
    is_s = cast("dict[str, cp_model.IntVar] | None", engine.structures.get("is_s"))
    if is_s is None:
        msg = "a Schrödinger pin needs a schrodinger layer, but the stack has none"
        raise MalformedPuzzleError(msg)
    for directive in directives:
        address = directive.address
        content = engine.contents(address)  # off-board raises here
        if isinstance(directive, SingletonPin):
            _require_in_domain(engine, address, (directive.digit,))
            engine.model.add(content[0] == directive.digit)
            engine.model.add(is_s[address] == 0)
        elif isinstance(directive, BareSingleton):
            engine.model.add(is_s[address] == 0)
        elif isinstance(directive, BareSCell):
            engine.model.add(is_s[address] == 1)
        elif isinstance(directive, HalfSCell):
            _require_in_domain(engine, address, (directive.digit,))
            holds = engine.reify_holds(content, directive.digit, f"half.{address}")
            engine.model.add_bool_or(holds)
            engine.model.add(is_s[address] == 1)
        else:
            low, high = sorted(directive.pair)
            _require_in_domain(engine, address, (low, high))
            engine.model.add(content[0] == low)
            engine.model.add(content[1] == high)
            engine.model.add(is_s[address] == 1)


def _require_in_domain(engine: Engine, address: str, digits: tuple[int, ...]) -> None:
    """Refuse a pin naming a digit the board never offered — the same content
    rule that governs a given or candidate (`engine.restrict`), but reaching
    both pair slots, which `restrict` (d0 only) cannot."""
    for digit in digits:
        if digit not in engine.board.values:
            values = list(engine.board.values)
            msg = f"digit {digit} is not among {values} for cell {address!r}"
            raise MalformedPuzzleError(msg)
