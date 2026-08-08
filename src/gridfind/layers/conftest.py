"""The read side of `emit`, for the layers package's tests (issue #100).

A layer emits **rules**, and one rule may cost many **solver constraints**
(`_base` documents the three levels). Nothing read those rules back, so a layer
test had only two ways to check its work: assert against the solver's raw
protocol buffer, or run a whole solve and infer the rule from the witness. The
first leaks solver internals into five test files; the second costs a solve per
assertion and cannot see a rule the witness happens to satisfy anyway.

These fixtures are that read side. Each takes a built engine and returns one
rule shape in gridfind's own vocabulary — cell addresses, groups, totals,
targets — never a protobuf message. A layer test says what the layer *meant*,
and the decoding lives here once.

This is a test seam, not engine surface: `emit` still writes straight to
`engine.model`, so the engine->layer contract (ADR-0001) does not move. It
becomes an `Engine` method the day a caller that is not a test wants it.
"""

from collections.abc import Callable, Iterator

import pytest

from gridfind.engine import Engine

# The marker `emit_distinct_count` gives the per-digit "this digit appears"
# bool: `<label>.present<digit>`. The rule that states the count is the one
# sum over those markers, so the marker is how the read side finds it.
_PRESENT = ".present"


def _address(variable_name: str) -> str:
    """The cell address a solver variable belongs to. `add_cell` names each
    variable `<address>.<position>`, so the address is everything before the
    final dot."""
    return variable_name.rsplit(".", 1)[0]


def _sums(engine: Engine) -> Iterator[tuple[list[str], int]]:
    """Every plain sum the engine holds, as the variable names it adds up and
    the total they must reach.

    Both the pair-sum rule and the counting rule state themselves as a sum
    fixed to one value; *what* they add up is what tells them apart, so this
    walk stays neutral and each fixture filters. Enforced sums are skipped —
    those are the reified per-cell equalities a counting rule computes with,
    not a rule any layer stated.
    """
    variables = engine.model.proto.variables
    for solver_constraint in engine.model.proto.constraints:
        if not solver_constraint.has_linear():
            continue
        if list(solver_constraint.enforcement_literal):
            continue
        names = [variables[var].name for var in solver_constraint.linear.vars]
        if names:
            yield names, solver_constraint.linear.domain[0]


@pytest.fixture
def cell_values() -> Callable[[Engine, str], list[int]]:
    """The digit values a cell may hold, ascending — `Board.values` as the
    engine actually gave it to one cell, rather than the two ends of it.

    A solver variable states its domain as flat pairs of closed intervals
    (`[low, high, low, high, ...]`). Every board gridfind builds today gives a
    cell one unbroken interval, so the multi-interval path here is decoded but
    not yet exercised — issue #102, which holds a cell to a stepped digit set,
    is what will exercise it.
    """

    def _values(engine: Engine, address: str) -> list[int]:
        domain = list(engine.cells[address].content[0].proto.domain)
        return [
            digit
            for low, high in zip(domain[::2], domain[1::2], strict=True)
            for digit in range(low, high + 1)
        ]

    return _values


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
        variables = engine.model.proto.variables
        return [
            [_address(variables[expr.vars[0]].name) for expr in rule.all_diff.exprs]
            for rule in engine.model.proto.constraints
            if rule.has_all_diff()
        ]

    return _groups


@pytest.fixture
def distinct_count_targets() -> Callable[[Engine], dict[str, int]]:
    """Every counting rule the engine holds, as its label mapped to the number
    of distinct digits it demands.

    One counting rule costs O(cells x digits) solver constraints, and only one
    of them states the count: a sum over the per-digit markers, fixed to the
    target. The rest are how that sum is computed, not what the rule says.
    """

    def _targets(engine: Engine) -> dict[str, int]:
        targets: dict[str, int] = {}
        for names, total in _sums(engine):
            if not all(_PRESENT in name for name in names):
                continue
            label = names[0].split(_PRESENT)[0]
            # A label is a rule's name here, so a repeat would silently drop
            # one rule from the answer. Say so instead.
            assert label not in targets, f"two counting rules are labelled {label!r}"
            targets[label] = total
        return targets

    return _targets


@pytest.fixture
def pair_sum_rules() -> Callable[[Engine], list[tuple[list[str], int]]]:
    """Every sum-over-cells rule the engine holds, as the cell addresses it
    adds up and the total they must reach, in emission order.

    A counting rule also states itself as a sum, but over per-digit markers
    rather than over cell content — the marker is what tells the two apart.
    """

    def _rules(engine: Engine) -> list[tuple[list[str], int]]:
        return [
            ([_address(name) for name in names], total)
            for names, total in _sums(engine)
            if not any(_PRESENT in name for name in names)
        ]

    return _rules
