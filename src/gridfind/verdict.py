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

from gridfind.engine import Engine, build_engine
from gridfind.layers import LAYER_REGISTRY, expand_constraints, resolve_constraints
from gridfind.puzzle import EMPTY, Candidate, Given, Placement, Puzzle, WorkingState
from gridfind.strategy import PURE_SATISFACTION, Strategy

VerdictKind = Literal["found", "broke", "unknown"]

DEFAULT_TIME_LIMIT_S = 10.0
DEFAULT_NUM_WORKERS = 8


@dataclass(frozen=True)
class Witness:
    """A found solve's digit per cell, paired with the board shape that read
    them (issue #72) — self-describing, so a consumer lays the grid out
    without re-deriving addressing. `assignment` stays reachable directly for
    a caller that wants one cell, not a render.

    It is an *assignment*, not `values`: `Board.values` is the digit domain a
    cell may hold, and one word for both the offer and the choice reads badly
    three lines apart."""

    grid: list[list[str]]
    assignment: dict[str, int]

    def __getitem__(self, name: str) -> int:
        return self.assignment[name]

    def __len__(self) -> int:
        return len(self.assignment)


@dataclass(frozen=True)
class Verdict:
    kind: VerdictKind
    witness: Witness | None = None


def verdict(
    puzzle: Puzzle,
    working_state: WorkingState = EMPTY,
    *,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    num_workers: int = DEFAULT_NUM_WORKERS,
    strategy: Strategy = PURE_SATISFACTION,
) -> Verdict:
    # board is not a constraint — the puzzle's board supplies the grid.
    # Expand presets and aliases once: the engine carries the canonical
    # constraints so a layer's constraints_of(name) matches the canonical
    # types the resolver dispatched on — an `x`/`v` clue reaches its
    # `pair-sum` layer as a sum-10/5 constraint.
    constraints = tuple(expand_constraints(puzzle.constraints))
    layers = [LAYER_REGISTRY["board"], *resolve_constraints(puzzle.constraints)]
    engine = build_engine(layers, constraints, board=puzzle.board)
    _apply(engine, puzzle.givens, working_state.places, working_state.candidates)
    strategy.configure(engine.model)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = num_workers
    status = solver.solve(engine.model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignment = {name: engine.value(solver, name) for name in engine.cells}
        grid = cast("list[list[str]]", engine.structures["grid"])
        return Verdict(kind="found", witness=Witness(grid=grid, assignment=assignment))
    if status == cp_model.INFEASIBLE:
        return Verdict(kind="broke")
    return Verdict(kind="unknown")


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
