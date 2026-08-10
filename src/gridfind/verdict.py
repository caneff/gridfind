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
from gridfind.layers.regions import region_map_for_constraints
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
from gridfind.witness import Witness

VerdictKind = Literal["found", "broke", "unknown"]

DEFAULT_TIME_LIMIT_S = 10.0
DEFAULT_NUM_WORKERS = 8


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
        region_map = region_map_for_constraints(canonical, puzzle.board.size)
        witness = Witness(grid=grid, assignment=assignment, region_map=region_map)
        return Verdict(kind="found", witness=witness)
    if status == cp_model.INFEASIBLE:
        return Verdict(kind="broke", reason=_region_reason(canonical, puzzle))
    return Verdict(kind="unknown")


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
    region_map = region_map_for_constraints(canonical, puzzle.board.size)
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
    """Fix the model from the structured givens and marks. A given stays
    literal to the cell's base slot (`d0 = d`) and a candidate restricts a
    cell to a digit subset — both go through the engine's one `restrict` call
    (issue #72). A placement diverges (issue #155): it refines to `d ∈
    content`, so it survives a digit landing on a Schrödinger S-cell's upper
    half — see `_apply_placement`."""
    for given in givens:
        engine.restrict(given.address, {given.digit})
    for placement in places:
        _apply_placement(engine, placement)
    for candidate in candidates:
        engine.restrict(candidate.address, candidate.digits)


def _apply_placement(engine: Engine, placement: Placement) -> None:
    """A placement fixes digit ∈ content — either slot — rather than `given`'s
    literal d0 = d (issue #155, spec #142's bare-placement refinement). On an
    ordinary board `content` is length 1, so this collapses to exactly the
    same `d0 == d` a given states; on a Schrödinger board it also honors a
    placement that a solve later reveals as an S-cell's upper half. Reuses
    the same reified-holds OR idiom the half-S-cell directive uses (#154) —
    `engine.reify_holds` over `engine.contents(address)` — rather than
    hand-rolling the membership OR. No `is_s` gate needed: the schrodinger
    layer's per-cell sentinel already makes `d1 == d` unsatisfiable for a
    singleton, so the OR collapses on its own."""
    address, digit = placement.address, placement.digit
    content = engine.contents(address)  # off-board raises here
    _require_in_domain(engine, address, (digit,))
    holds = engine.reify_holds(content, digit, f"placement.{address}")
    engine.model.add_bool_or(holds)


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
