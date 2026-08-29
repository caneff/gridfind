"""The `schrodinger` layer: an S-cell's second digit, discovered by solving
(CONTEXT.md `schrodinger` layer).

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

Also owns each S-cell's **value**, since it is the layer that widens a cell to
two digits (ADR-0009 decision 4). Just as the doubler reifies a cell's value
into the `"modifier_value"` channel, this layer reifies each cell's value into
the `"s_value"` channel — its `d0` when a singleton, its two digits summed
when an S-cell — so a values-distinct reader reads one value, blind to how it
was built (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from gridfind.engine import Engine, MalformedPuzzleError


@dataclass
class Schrodinger:
    """Gives every cell a second content slot (`d1`), so a reader of a cell
    faces a digit set rather than one digit. Every layer declares how it
    reads that pair — value or digit (ADR-0019) — so any layer composes with
    this one."""

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
        low = board.values[0]
        high = board.values[-1]
        ceiling = high + high
        is_s: dict[str, cp_model.IntVar] = {}
        s_value: dict[str, cp_model.IntVar] = {}
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
            # This cell's value: d0 as a singleton, the two digits summed as
            # an S-cell — reified on is_s, mirroring the doubler's channel.
            combined = d0 + d1
            value = engine.model.new_int_var(low, ceiling, f"{address}.s_value")
            engine.model.add(value == combined).only_enforce_if(s)
            engine.model.add(value == d0).only_enforce_if(s.negated())
            s_value[address] = value
        engine.register_structure("is_s", is_s)
        engine.register_structure("s_value", s_value)

    def emit(self, engine: Engine) -> None:
        pass
