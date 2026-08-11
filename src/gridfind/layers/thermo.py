"""The `thermo` layer: gridfind's first line type.

A thermo clue names an **ordered** path of cells, bulb first, and holds each
consecutive pair to a directed inequality: strict `a < b` for a normal
thermo, non-strict `a <= b` for a slow one (repeats allowed, so a slow line
has no length ceiling). A two-cell path is a single directed edge — the
degenerate inequality case falls out for free, no separate primitive needed
("inequality is the degenerate length-2 thermo").

Positive-only, distinctness-free: the rule never asks whether a path's cells
share a house, and states no implied `add_all_different` — that is `cage`'s
job, matching `pair-difference`'s precedent. Modeled directly on CP-SAT's
native `<` rather than a reified either-or or a hand-built truth table
(ADR-0001 keeps the engine seam raw OR-Tools): a thermo edge is directed, so
there is nothing a table would buy.

The per-edge emission decomposes the path into consecutive pairs itself, then
hands them to the shared `emit_over_pairs` walk `pair-sum`/`pair-difference`
already use — no new generic path-walk primitive, matching the spec's "build
nothing generic now." A second line type (whisper, renban) can still lift a
shared walk out later if one actually needs it.

The `slow` flag rides on every clue's params (decoded by `sudokumaker.py`)
and picks the edge relation: `≤` when true, `<` otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine
from gridfind.layers._base import emit_over_pairs


def _strictly_increasing(
    engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar
) -> None:
    engine.model.add(a < b)


def _non_decreasing(engine: Engine, a: cp_model.IntVar, b: cp_model.IntVar) -> None:
    engine.model.add(a <= b)


@dataclass
class Thermo:
    name: str = "thermo"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            # params is the open JSON boundary (object) — narrow to this
            # clue's shape: an ordered path of cell addresses plus the
            # normal/slow flavor flag.
            path = cast("list[str]", clue.params["path"])
            slow = cast("bool", clue.params["slow"])
            pairs = [(engine.content(a), engine.content(b)) for a, b in pairwise(path)]
            rel = _non_decreasing if slow else _strictly_increasing
            emit_over_pairs(engine, pairs, rel)
