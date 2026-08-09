"""The `schrodinger` layer: an S-cell's second digit, discovered by solving
(spec #139, decisions #131/#133; CONTEXT.md `schrodinger` layer).

Widens every grid cell to a length-2 content sequence `[d0, d1]`: `d0` is
always a real digit; `d1` is a real digit or a per-cell sentinel above every
real digit; `is_S <=> d1` is real; `d0 < d1` canonicalizes an S-cell's pair
(and is trivially true for a singleton, whose `d1` sentinel always exceeds
`d0`). Bare `{type: schrodinger}` — no data, like `sudoku` — registered as
one plain layer (no preset, no alias).

Owns only the widening. "Exactly `k = len(values) - size` S-cells per house"
is not stated here — it emerges from `distinct.DistinctOverGroups`' own
is_S-gated counting rule, once this layer's `is_s` structure tells that rule
a cell carries a second slot to gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from gridfind.engine import Engine, MalformedPuzzleError


@dataclass
class Schrodinger:
    name: str = "schrodinger"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        board = engine.board
        if len(board.values) <= board.size:
            msg = (
                f"schrodinger needs more digit values than the board size "
                f"({board.size}) to force an S-cell, got {len(board.values)}"
            )
            raise MalformedPuzzleError(msg)
        high = board.values[-1]
        is_s: dict[str, cp_model.IntVar] = {}
        for index, address in enumerate(engine.cells):
            content = engine.contents(address)
            d0 = content[0]
            sentinel = high + 1 + index
            domain = cp_model.Domain.from_values([*board.values, sentinel])
            d1 = engine.model.new_int_var_from_domain(domain, f"{address}.1")
            s = engine.model.new_bool_var(f"{address}.is_s")
            engine.model.add(d1 <= high).only_enforce_if(s)
            engine.model.add(d1 > high).only_enforce_if(s.negated())
            # Canonicalizes an S-cell's unordered pair. Also holds trivially
            # for a singleton: d1's sentinel is always > high >= d0.
            engine.model.add(d0 < d1)
            content.append(d1)
            is_s[address] = s
        engine.register_structure("is_s", is_s)

    def emit(self, engine: Engine) -> None:
        pass
