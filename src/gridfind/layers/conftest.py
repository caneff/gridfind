"""The read side of `emit`, shared by the layers package's tests (issue #100).

A layer emits **rules**, and one rule may cost many **solver constraints**
(`_base` documents the three levels). Nothing read those rules back, so a layer
test had to assert against the solver's protocol buffer or pay for a whole
solve. These functions are that read side: each returns one rule shape in
gridfind's own vocabulary — addresses, groups, totals, targets.

They live in `conftest.py` because more than one test module needs them and the
wheel already excludes this shape (`pyproject.toml` `source-exclude`). They are
plain functions, not fixtures: a fixture whose whole body is `return _f` buys
nothing over an import.

This is a test seam, not engine surface. `emit` still writes straight to
`engine.model`, so the engine->layer contract (ADR-0001) does not move.
"""

from collections.abc import Iterator

from gridfind.engine import Engine


def _cell_addresses(engine: Engine) -> dict[int, str]:
    """Which cell each solver variable belongs to, by variable index.

    Built from `engine.cells` rather than by parsing variable names, so what
    counts as cell content is a structural fact. Renaming a variable cannot
    make one kind of rule read back as another.
    """
    return {
        variable.index: address
        for address, cell in engine.cells.items()
        for variable in cell.content
    }


def _sums(engine: Engine) -> Iterator[tuple[list[int], int]]:
    """Every plain sum the engine holds, as the variable indices it adds up
    and the total they must reach.

    Enforced sums are skipped: those are the reified per-cell equalities a
    counting rule computes with, not a rule a layer stated.
    """
    for solver_constraint in engine.model.proto.constraints:
        if not solver_constraint.has_linear():
            continue
        if list(solver_constraint.enforcement_literal):
            continue
        variables = list(solver_constraint.linear.vars)
        if variables:
            yield variables, solver_constraint.linear.domain[0]


def cell_values(engine: Engine, address: str) -> list[int]:
    """The digit values a cell may hold, ascending — `Board.values` as the
    engine gave it to one cell, rather than the two ends of it. Reads through
    `Engine.domain`, the one home for decoding a cell's solver domain (issue
    #104)."""
    return engine.domain(address)


def all_different_groups(engine: Engine) -> list[list[str]]:
    """Every all-different rule, as the cell addresses in its group.

    Reads the first variable of each expression: gridfind emits
    `add_all_different` over plain cell content, so one expression is one cell.
    """
    address_of = _cell_addresses(engine)
    return [
        [address_of[expr.vars[0]] for expr in rule.all_diff.exprs]
        for rule in engine.model.proto.constraints
        if rule.has_all_diff()
    ]


def pair_sum_rules(engine: Engine) -> list[tuple[list[str], int]]:
    """Every sum-over-cells rule, as the addresses it adds up and the total
    they must reach. A sum over cell content is this rule; a counting rule
    sums per-digit markers instead."""
    address_of = _cell_addresses(engine)
    return [
        ([address_of[variable] for variable in variables], total)
        for variables, total in _sums(engine)
        if all(variable in address_of for variable in variables)
    ]


def distinct_count_targets(engine: Engine) -> dict[str, int]:
    """Every counting rule, as its label mapped to the number of distinct
    digits it demands.

    One counting rule costs O(cells x digits) solver constraints, and only one
    states the count: the sum over its per-digit markers. The label is a naming
    convention (`<label>.present<digit>`), so it is the one thing here read off
    a variable's name.
    """
    address_of = _cell_addresses(engine)
    names = engine.model.proto.variables
    targets: dict[str, int] = {}
    for variables, total in _sums(engine):
        if any(variable in address_of for variable in variables):
            continue
        label = names[variables[0]].name.rsplit(".", 1)[0]
        # A label names a rule, so a repeat would silently drop one from the
        # answer. Say so instead.
        assert label not in targets, f"two counting rules are labelled {label!r}"
        targets[label] = total
    return targets
