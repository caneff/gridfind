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

`verdict()` keeps only assemble-solve-classify (issue #208): applying the
working state onto the model is `gridfind.applier.apply`, and the broke-path
diagnosis is `gridfind.layers.regions.reason`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ortools.sat.python import cp_model

from gridfind.applier import apply
from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.regions import reason, region_map_for_constraints
from gridfind.puzzle import EMPTY, Puzzle, WorkingState
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
    canonical, layer_stack = build_stack(puzzle.constraints, size=puzzle.board.size)
    engine = build_engine(layer_stack, tuple(canonical), board=puzzle.board)
    apply(engine, puzzle, working_state)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = num_workers
    status = solver.solve(engine.model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        is_s = engine.is_s()
        assignment: dict[str, tuple[int, ...]] = {}
        for address in engine.cells:
            content = engine.values(solver, address)
            is_this_s = is_s is not None and bool(solver.value(is_s[address]))
            assignment[address] = content if is_this_s else content[:1]
        grid = engine.grid()
        region_map = region_map_for_constraints(canonical, puzzle.board.size)
        witness = Witness(grid=grid, assignment=assignment, region_map=region_map)
        return Verdict(kind="found", witness=witness)
    if status == cp_model.INFEASIBLE:
        return Verdict(kind="broke", reason=reason(puzzle))
    return Verdict(kind="unknown")
