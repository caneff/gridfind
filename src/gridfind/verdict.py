"""The one seam: verdict(puzzle, working_state=EMPTY) -> found | broke | unknown.

Races a broke-proof against a witness-find by handing CP-SAT's portfolio
solver a pure-satisfaction model — whichever is decidable first is what the
single `solve` call returns (spec #4, decisions 15, 15a, 32).

The input is the structured `Puzzle` + `WorkingState` (spec #45, issue #48):
the puzzle's variant records resolve to layers (issue #47), its board supplies
the grid, and givens/places/candidates pin the model. Pinning one puzzle and
racing many working states reuses the puzzle value — no new API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ortools.sat.python import cp_model

from gridfind.engine import Engine, build_engine
from gridfind.layers import LAYER_REGISTRY, resolve_records
from gridfind.layers._base import MAX_DIGIT, MIN_DIGIT
from gridfind.puzzle import EMPTY, Candidate, Given, Place, Puzzle, WorkingState
from gridfind.strategy import PURE_SATISFACTION, Strategy

VerdictKind = Literal["found", "broke", "unknown"]

DEFAULT_TIME_LIMIT_S = 10.0
DEFAULT_NUM_WORKERS = 8

# A given or mark outside the board's digit domain ([MIN_DIGIT, MAX_DIGIT], the
# same range board.py builds its cells over) is a bad address into the model,
# rejected here rather than left to solve as silently infeasible.


@dataclass(frozen=True)
class Verdict:
    kind: VerdictKind
    witness: dict[str, int] | None = None


def verdict(
    puzzle: Puzzle,
    working_state: WorkingState = EMPTY,
    *,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    num_workers: int = DEFAULT_NUM_WORKERS,
    strategy: Strategy = PURE_SATISFACTION,
) -> Verdict:
    # board is not a variant record — the puzzle's board supplies the grid.
    # ponytail: the board layer is a fixed 9x9 (board.py BOARD_SIZE); puzzle's
    # board.size isn't wired yet, so a non-9 board still solves as 9x9. Wire it
    # through when a second board size lands.
    layers = [LAYER_REGISTRY["board"], *resolve_records(puzzle.variants)]
    engine = build_engine(layers)
    _apply(engine, puzzle.givens, working_state.places, working_state.candidates)
    strategy.configure(engine.model)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = num_workers
    status = solver.solve(engine.model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        witness = {
            name: solver.value(cell.content[0]) for name, cell in engine.cells.items()
        }
        return Verdict(kind="found", witness=witness)
    if status == cp_model.INFEASIBLE:
        return Verdict(kind="broke")
    return Verdict(kind="unknown")


def _apply(
    engine: Engine,
    givens: tuple[Given, ...],
    places: tuple[Place, ...],
    candidates: tuple[Candidate, ...],
) -> None:
    """Pin the model from the structured givens and marks. A given and a place
    both fix one digit; a candidate restricts a cell to a digit subset."""
    for pin in (*givens, *places):
        var = _cell_var(engine, pin.address)
        _check_digit(pin.digit)
        engine.model.add(var == pin.digit)
    for candidate in candidates:
        var = _cell_var(engine, candidate.address)
        for digit in candidate.digits:
            _check_digit(digit)
        allowed = [(digit,) for digit in sorted(candidate.digits)]
        engine.model.add_allowed_assignments([var], allowed)


def _cell_var(engine: Engine, address: str) -> cp_model.IntVar:
    cell = engine.cells.get(address)
    if cell is None:
        msg = f"address {address!r} is off the board"
        raise ValueError(msg)
    (var,) = cell.content
    return var


def _check_digit(digit: int) -> None:
    if not MIN_DIGIT <= digit <= MAX_DIGIT:
        msg = f"digit {digit} out of range [{MIN_DIGIT}, {MAX_DIGIT}]"
        raise ValueError(msg)
