"""The verdict seam: verdict(puzzle) -> found | broke | unknown, and
enumerate_witnesses(puzzle, limit=N) -> up to N distinct completions.

Races a broke-proof against a witness-find by handing CP-SAT's portfolio
solver a pure-satisfaction model — whichever is decidable first is what the
single `solve` call returns (decisions 15, 15a, 32).

The input is the structured `Puzzle` + `WorkingState`:
the puzzle's constraints resolve to layers, its board supplies
the grid, and givens/placements/candidates fix the model. Each call rebuilds the
engine from scratch — the build is ~1% of a solve, and no caller races many
working states over one puzzle, so no build-once/race-many API is offered
(ADR-0002).

`verdict()` keeps only assemble-solve-classify: applying the
working state onto the model is `gridfind.applier.apply`, and the broke-path
diagnosis is `gridfind.layers.regions.reason`. `_build_and_solve` is the shared
build-and-solve core: `verdict()` classifies its raw result directly, and
`enumerate_witnesses()` (spec #389, decision #20) reuses the same core for its
phase 1, so the two functions cannot drift in how they assemble or apply the
puzzle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from ortools.sat.python import cp_model

from gridfind.applier import apply
from gridfind.engine import Engine, build_engine
from gridfind.layers import build_stack
from gridfind.layers.regions import RegionMap, reason, region_map_for_constraints
from gridfind.puzzle import EMPTY, Constraint, Puzzle, WorkingState
from gridfind.witness import Witness

VerdictKind = Literal["found", "broke", "unknown"]

DEFAULT_TIME_LIMIT_S = 10.0
DEFAULT_NUM_WORKERS = 8


@dataclass(frozen=True)
class _BuildSolveResult:
    """The raw materials of a build-and-solve, unclassified."""

    engine: Engine
    solver: cp_model.CpSolver
    status: cp_model.CpSolverStatus
    canonical: tuple[Constraint, ...]


def _build_and_solve(
    puzzle: Puzzle,
    working_state: WorkingState,
    *,
    time_limit_s: float,
    num_workers: int,
) -> _BuildSolveResult:
    """Build the puzzle, apply the working state, and race a broke-proof
    against a witness-find. Returns the raw engine/solver/status/constraints
    for the caller to classify."""
    # board is not a constraint — the puzzle's board supplies the grid. The
    # door expands presets and aliases exactly once and hands back both the
    # canonical constraints (so a layer's constraints_of(name) matches the
    # canonical types dispatch resolved on — an `x`/`v` clue reaches its
    # `group-sum` layer as a sum-10/5 constraint) and the stack, compulsory
    # `board` layer already in it.
    canonical, layer_stack = build_stack(puzzle.constraints, size=puzzle.board.size)
    engine = build_engine(layer_stack, tuple(canonical), board=puzzle.board)
    apply(engine, puzzle, working_state)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = num_workers
    status = solver.solve(engine.model)

    return _BuildSolveResult(
        engine=engine, solver=solver, status=status, canonical=tuple(canonical)
    )


@dataclass(frozen=True)
class Verdict:
    """`reason` is the broke witness's one explanation: set when a region in the
    resolved partition falls outside the
    cover feasibility band — outgrows the digit domain (`cells > domain`) or
    is too small to cover it even with Schrodinger S-cells (`domain >
    2*cells`) — either a fact that alone proves no completion exists. `None`
    on every other broke (an ordinary contradiction has no region to blame)
    and on found/unknown alike."""

    kind: VerdictKind
    witness: Witness | None = None
    reason: str | None = None


def _witness_from(
    engine: Engine, solver: cp_model.CpSolver, region_map: RegionMap
) -> Witness:
    """Read one solution off the engine into a `Witness`. Both `verdict()`'s
    found-path and `enumerate_witnesses()`'s phase-2 collector build the witness
    this one way, so a change to what a witness carries (T3 widens its identity)
    lands in a single place. `solver` is any reader over the solution — a
    `CpSolver` or the solution callback standing in for one."""
    return Witness(
        grid=engine.grid(),
        assignment=engine.assignment(solver),
        region_map=region_map,
        modifiers=engine.discovered_modifiers(solver),
    )


def verdict(
    puzzle: Puzzle,
    working_state: WorkingState = EMPTY,
    *,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    num_workers: int = DEFAULT_NUM_WORKERS,
) -> Verdict:
    solved = _build_and_solve(
        puzzle, working_state, time_limit_s=time_limit_s, num_workers=num_workers
    )

    if solved.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        region_map = region_map_for_constraints(solved.canonical, puzzle.board.size)
        witness = _witness_from(solved.engine, solved.solver, region_map)
        return Verdict(kind="found", witness=witness)
    if solved.status == cp_model.INFEASIBLE:
        return Verdict(kind="broke", reason=reason(puzzle))
    return Verdict(kind="unknown")


@dataclass(frozen=True)
class Enumeration:
    """`enumerate_witnesses()`'s answer: up to `limit` distinct completions.

    `witnesses` are pairwise distinct on their identity (two completions differ
    iff their full per-cell assignment differs — ADR-0015). `exhaustive` is
    True only when phase 2 proved it saw every completion, so it went unstopped
    by the `limit`. `reason` carries the broke explanation `verdict()` gives,
    None otherwise. There is deliberately no singular `.witness` accessor: an
    exact-count question must not degrade into "give me one and drop the rest"
    (decisions #382, #385)."""

    kind: VerdictKind
    witnesses: tuple[Witness, ...] = ()
    exhaustive: bool = False
    reason: str | None = None


class _WitnessCollector(cp_model.CpSolverSolutionCallback):
    """Collects distinct witnesses from phase 2's `enumerate_all_solutions`
    stream, dedups them on the identity tuple, and stops the search once
    `limit` have landed. A solution callback reads a solution through the same
    `.value()` seam a `CpSolver` does, so it stands in for one where the engine
    reads an assignment — the read stays single-sourced in `engine`."""

    def __init__(self, engine: Engine, region_map: RegionMap, limit: int) -> None:
        super().__init__()
        self._engine = engine
        self._region_map = region_map
        self._limit = limit
        self._seen: set[tuple[int, ...]] = set()
        self.witnesses: list[Witness] = []

    def on_solution_callback(self) -> None:
        reader = cast("cp_model.CpSolver", self)
        identity = tuple(
            reader.value(self._engine.d0(address)) for address in self._engine.cells
        )
        if identity in self._seen:
            return
        self._seen.add(identity)
        self.witnesses.append(_witness_from(self._engine, reader, self._region_map))
        if len(self.witnesses) >= self._limit:
            self.stop_search()


def enumerate_witnesses(
    puzzle: Puzzle,
    working_state: WorkingState = EMPTY,
    *,
    limit: int,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    num_workers: int = DEFAULT_NUM_WORKERS,
) -> Enumeration:
    """Up to `limit` distinct completions of the puzzle. Phase 1 is the same
    portfolio solve `verdict()` runs; only a `found` phase 1 reaches phase 2,
    which re-solves the same model with `enumerate_all_solutions` and collects
    distinct witnesses. One wall budget spans both phases — phase 2 gets what
    phase 1 left."""
    if limit <= 0:
        msg = f"limit must be positive, got {limit}"
        raise ValueError(msg)

    solved = _build_and_solve(
        puzzle, working_state, time_limit_s=time_limit_s, num_workers=num_workers
    )
    if solved.status == cp_model.INFEASIBLE:
        return Enumeration(kind="broke", reason=reason(puzzle))
    if solved.status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Enumeration(kind="unknown")

    region_map = region_map_for_constraints(solved.canonical, puzzle.board.size)
    collector = _WitnessCollector(solved.engine, region_map, limit)
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_workers = 1
    solver.parameters.symmetry_level = 0
    solver.parameters.max_time_in_seconds = max(
        0.0, time_limit_s - solved.solver.wall_time
    )
    status = solver.solve(solved.engine.model, collector)

    return Enumeration(
        kind="found",
        witnesses=tuple(collector.witnesses),
        exhaustive=status == cp_model.OPTIMAL,
    )
