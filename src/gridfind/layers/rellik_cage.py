"""The `rellik-cage` layer: an anti-cage subset-sum ban.

A rellik (anti-) cage forbids any non-empty group of its cells from summing
to a chosen forbidden total — the reference solver's Rellik rule.
Uniqueness is not this layer's job: a
rellik cage is a `cage` (`distinct-over: "digit"`) composed alongside this
layer over the same cells, exactly as a killer cage composes `cage` with
`group-sum` (ADR-0009) — this layer states no distinctness rule and reads
no `distinct-over` param.

One stateless `rellik-cage` instance pulls every such constraint via
`constraints_of` and emits one `sum(group) != target` per surviving group,
a clue-looping layer structured like `cage`/`group-sum`. Arithmetic reads
each cell through `Engine.value_expr` (ADR-0009), so a doubler or S-cell
inside the cage counts by its worth — the same value channel a killer
`group-sum` reads, uniform across every sum-shaped rule in the repo.

Every non-empty subset of a cage's cells is a candidate group, but not
every subset can possibly reach the target — enumerating and ruling out
all `2^n - 1` of them is wasted model size once a cage grows. The
size-band prune drops a whole size class at once: a group of size `k` can
reach `target` only if `target` falls within the sum of the `k` smallest
and `k` largest per-cell value bounds across the cage's own cells (read off
each cell's own `value_expr` domain, so a modifier's widened range is
already accounted for). This is a **sound over-approximation** — it never
assumes the composed `cage`'s distinctness, so it never drops a group that
could reach the target even where a setter left the no-repeats half off
(the correctness floor). A tighter, distinct-digit-aware
band is available as a future optimization if a real puzzle's group count
ever bites; this ships the sound version only.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import Engine


def _value_bounds(engine: Engine, address: str) -> tuple[int, int]:
    """A cell's own `value_expr` range, read off its solver domain — the
    per-cell bound the size-band prune sums across a group, blind to
    whether that range came from a plain digit, a doubler's folded value, or
    an S-cell's `s_value` (the domain already reflects whichever channel
    built it)."""
    domain = cast("cp_model.IntVar", engine.value_expr(address)).proto.domain
    return min(domain), max(domain)


@dataclass
class RellikCage:
    """An anti-cage: forbids any non-empty subset of its named cells from
    summing to a chosen forbidden target; states no distinctness of its own."""

    name: str = "rellik-cage"
    depends_on: tuple[str, ...] = ("board",)

    def register(self, engine: Engine) -> None:
        pass

    def emit(self, engine: Engine) -> None:
        for clue in engine.constraints_of(self.name):
            addresses = engine.cell_addresses(clue)
            target = cast("int", clue.params["sum"])
            self._emit_clue(engine, addresses, target)

    def _emit_clue(self, engine: Engine, addresses: list[str], target: int) -> None:
        bounds = [_value_bounds(engine, address) for address in addresses]
        smallest_lows = sorted(low for low, _ in bounds)
        largest_highs = sorted((high for _, high in bounds), reverse=True)
        for size in range(1, len(addresses) + 1):
            min_reachable = sum(smallest_lows[:size])
            max_reachable = sum(largest_highs[:size])
            if not (min_reachable <= target <= max_reachable):
                continue
            for group in itertools.combinations(addresses, size):
                terms = [engine.value_expr(address) for address in group]
                engine.model.add(sum(terms) != target)
