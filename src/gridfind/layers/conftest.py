"""The read side of `emit`, for the layers package's tests (issue #100).

A layer emits **rules**, and one rule may cost many **solver constraints**
(`_base` documents the three levels). Nothing reads those rules back, so a
layer test had only two ways to check its work: assert against the solver's
raw protocol buffer, or run a whole solve and infer the rule from the witness.
The first leaks solver internals into five test files; the second costs a solve
per assertion and cannot see a rule the witness happens to satisfy anyway.

These fixtures are that read side. Each takes a built engine and returns one
rule shape in gridfind's own vocabulary — cell addresses, groups, totals,
targets — never a protobuf message. A layer test says what the layer *meant*,
and the decoding lives here once.

This is a test seam, not engine surface: `emit` still writes straight to
`engine.model`, so the engine->layer contract (ADR-0001) does not move. It
becomes an `Engine` method the day a caller that is not a test wants it.
"""

from collections.abc import Callable

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import Engine


def _address_of(model: cp_model.CpModel, index: int) -> str:
    """The cell address a solver variable belongs to. `add_cell` names each
    variable `<address>.<position>`, so the address is everything before the
    final dot."""
    return model.proto.variables[index].name.rsplit(".", 1)[0]


@pytest.fixture
def cell_digits() -> Callable[[Engine, str], list[int]]:
    """The digits a cell may hold, ascending — the set a layer gave it, not
    the two ends of that set.

    A solver variable states its domain as flat pairs of closed intervals
    (`[low, high, low, high, ...]`), so a domain with a gap in it reads back
    honestly here rather than collapsing to its bounds.
    """

    def _digits(engine: Engine, address: str) -> list[int]:
        domain = list(engine.cells[address].content[0].proto.domain)
        return [
            digit
            for low, high in zip(domain[::2], domain[1::2], strict=True)
            for digit in range(low, high + 1)
        ]

    return _digits


@pytest.fixture
def all_different_groups() -> Callable[[Engine], list[list[str]]]:
    """Every all-different rule the engine holds, as the cell addresses in
    each group, in emission order.

    Reads the first variable of each expression: gridfind emits
    `add_all_different` over plain cell content, so one expression is one cell.
    A layer emitting an all-different over compound expressions would need more
    here — none does.
    """

    def _groups(engine: Engine) -> list[list[str]]:
        return [
            [_address_of(engine.model, expr.vars[0]) for expr in rule.all_diff.exprs]
            for rule in engine.model.proto.constraints
            if rule.has_all_diff()
        ]

    return _groups


# The marker `emit_distinct_count` gives the per-digit "this digit appears"
# bool: `<label>.present<digit>`. The rule that states the count is the one
# sum over those markers, so the marker is how the read side finds it.
_PRESENT = ".present"


@pytest.fixture
def distinct_count_targets() -> Callable[[Engine], dict[str, int]]:
    """Every counting rule the engine holds, as its label mapped to the number
    of distinct digits it demands.

    One counting rule costs O(cells x digits) solver constraints, and only one
    of them states the count: an unenforced sum over the per-digit markers,
    fixed to the target. The rest — the reified per-cell equalities and the
    per-digit maximums — are how that sum is computed, not what the rule says.
    """

    def _targets(engine: Engine) -> dict[str, int]:
        model = engine.model
        targets: dict[str, int] = {}
        for rule in model.proto.constraints:
            if not rule.has_linear() or list(rule.enforcement_literal):
                continue
            names = [model.proto.variables[var].name for var in rule.linear.vars]
            if not names or not all(_PRESENT in name for name in names):
                continue
            label = names[0].split(_PRESENT)[0]
            targets[label] = rule.linear.domain[0]
        return targets

    return _targets


@pytest.fixture
def pair_sum_rules() -> Callable[[Engine], list[tuple[list[str], int]]]:
    """Every sum-over-cells rule the engine holds, as the cell addresses it
    sums and the total they must reach, in emission order.

    A counting rule also states itself as a sum, but over per-digit markers
    rather than over cell content — the marker is what tells the two apart.
    """

    def _rules(engine: Engine) -> list[tuple[list[str], int]]:
        model = engine.model
        found: list[tuple[list[str], int]] = []
        for rule in model.proto.constraints:
            if not rule.has_linear() or list(rule.enforcement_literal):
                continue
            names = [model.proto.variables[var].name for var in rule.linear.vars]
            if not names or any(_PRESENT in name for name in names):
                continue
            addresses = [name.rsplit(".", 1)[0] for name in names]
            found.append((addresses, rule.linear.domain[0]))
        return found

    return _rules
