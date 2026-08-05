"""The one seam: verdict(stack, working_state_text) -> found | broke | unknown.

Races a broke-proof against a witness-find by handing CP-SAT's portfolio
solver a pure-satisfaction model — whichever is decidable first is what the
single `solve` call returns (spec #4, decisions 15, 15a, 32).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import expand_stack, resolve
from gridfind.strategy import PURE_SATISFACTION, Strategy
from gridfind.working_state import apply, parse

VerdictKind = Literal["found", "broke", "unknown"]

DEFAULT_TIME_LIMIT_S = 10.0
DEFAULT_NUM_WORKERS = 8


@dataclass(frozen=True)
class Verdict:
    kind: VerdictKind
    witness: dict[str, int] | None = None


def verdict(
    stack: str | list[str],
    working_state_text: str,
    *,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    num_workers: int = DEFAULT_NUM_WORKERS,
    strategy: Strategy = PURE_SATISFACTION,
) -> Verdict:
    working_state = parse(working_state_text)
    requested_layers = expand_stack(stack)
    if set(expand_stack(working_state.stack)) != set(requested_layers):
        msg = (
            "working-state header stack "
            f"{working_state.stack!r} does not match requested stack {stack!r}"
        )
        raise ValueError(msg)

    engine = build_engine(resolve(requested_layers))
    apply(engine, working_state)
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
