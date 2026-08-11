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
from typing import cast

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
    """A cell's own bounds, ascending, read through `Engine.domain` — the one
    home for decoding a cell's solver domain (issue #104).

    Not the declared value set itself: a stepped `Board.values` (issue #102)
    is made authoritative by `restrict`'s AllowedAssignments table, a
    constraint alongside the variable rather than a rewrite of its domain, so
    a cell's bounds stay the two ends even when the values between them are
    excluded. Read the table back to see the excluded gaps.
    """
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


def _abs_equality_targets(engine: Engine) -> dict[int, tuple[int, int]]:
    """Every `add_abs_equality`'s target variable index, mapped to the two
    operand variable indices its difference is over.

    Read structurally off the `lin_max` proto both `add_abs_equality` and
    `add_max_equality` compile to (`pair-difference`'s aux var and a counting
    rule's per-digit `present` indicator, respectively) — the two uses are
    told apart by shape, not by name: an abs equality's `lin_max` carries two
    exprs, each holding *both* operand vars (one `a - b`, one `b - a`); a max
    equality's carries one var per expr instead. Only the two-var shape is an
    abs equality.
    """
    targets: dict[int, tuple[int, int]] = {}
    for constraint in engine.model.proto.constraints:
        if not constraint.has_lin_max():
            continue
        exprs = constraint.lin_max.exprs
        if len(exprs) != 2 or any(len(expr.vars) != 2 for expr in exprs):
            continue
        target_var = constraint.lin_max.target.vars[0]
        a_index, b_index = exprs[0].vars
        targets[target_var] = (a_index, b_index)
    return targets


def pair_difference_rules(engine: Engine) -> list[tuple[list[str], int]]:
    """Every pair-difference rule, as the pair's addresses and its target
    `k`. Reads the `lin_max` `add_abs_equality` produces for its aux var `d`
    structurally (`_abs_equality_targets`), then `d`'s pinning `d == k`
    off the same single-var-sum seam `distinct_count_targets` reads its
    counting totals from."""
    address_of = _cell_addresses(engine)
    pins = {
        variables[0]: total for variables, total in _sums(engine) if len(variables) == 1
    }
    return [
        ([address_of[a_index], address_of[b_index]], pins[target_var])
        for target_var, (a_index, b_index) in _abs_equality_targets(engine).items()
        if target_var in pins
    ]


def _pair_ratio_targets(engine: Engine) -> dict[int, tuple[int, int, int]]:
    """Every pair-ratio reified either-or, keyed by its indicator bool's
    variable index, to the two operand variable indices and the target `k`.

    Read structurally off the enforced-linear-equality pair `ratio_of`'s
    `rel` emits: two two-var linear constraints sharing one enforcement
    literal's variable, one on the positive literal (`a == k*b`) and one on
    its negation (`b == k*a`). Only the positive branch is read — it already
    carries `a`, `b`, and `k` — so `d1 <= high`-shaped single-var reified
    constraints (`schrodinger`'s `is_s` gate) never match: this filter
    requires exactly two vars with a coefficient of `1` on one of them, a
    shape those single-var constraints don't have.
    """
    targets: dict[int, tuple[int, int, int]] = {}
    for constraint in engine.model.proto.constraints:
        if not constraint.has_linear():
            continue
        literals = list(constraint.enforcement_literal)
        if len(literals) != 1 or literals[0] < 0:
            continue
        linear = constraint.linear
        if len(linear.vars) != 2:
            continue
        v0, v1 = linear.vars
        c0, c1 = linear.coeffs
        if c0 == 1:
            a_index, b_index, k = v0, v1, -c1
        elif c1 == 1:
            a_index, b_index, k = v1, v0, -c0
        else:
            continue
        targets[literals[0]] = (a_index, b_index, k)
    return targets


def pair_ratio_rules(engine: Engine) -> list[tuple[list[str], int]]:
    """Every pair-ratio rule, as the pair's addresses and its target `k`.
    Reads the reified either-or's canonical (`a == k*b`) branch structurally
    (`_pair_ratio_targets`) — the one non-trivial shape `pair-ratio` adds
    over `pair-difference`'s single `add_abs_equality`."""
    address_of = _cell_addresses(engine)
    return [
        ([address_of[a_index], address_of[b_index]], k)
        for a_index, b_index, k in _pair_ratio_targets(engine).values()
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


def _strict_less_pairs(engine: Engine) -> list[tuple[int, int]]:
    """Every strict `a < b` solver constraint, as its two operand variable
    indices, in emission order.

    Read structurally off the compiled linear form CP-SAT's `add(a < b)`
    produces: two vars with coefficients `[1, -1]` and a domain closed at
    `-1` (`a - b <= -1`) — distinct in shape from a plain sum's `[1, 1]`
    coefficients and single-value domain (`_sums`), and from `add_abs_equality`'s
    `lin_max` form (`_abs_equality_targets`).
    """
    pairs: list[tuple[int, int]] = []
    for constraint in engine.model.proto.constraints:
        if not constraint.has_linear():
            continue
        if list(constraint.enforcement_literal):
            continue
        lin = constraint.linear
        variables = list(lin.vars)
        domain = list(lin.domain)
        if list(lin.coeffs) == [1, -1] and domain[-1:] == [-1]:
            pairs.append((variables[0], variables[1]))
    return pairs


def thermo_rules(engine: Engine) -> list[list[tuple[str, str]]]:
    """Every thermo rule, grouped by clue, as each consecutive pair's
    addresses in path order.

    Reads the strict edges structurally (`_strict_less_pairs`), then regroups
    them by each clue's own path length in emission order — `Thermo.emit`
    walks `constraints_of` in order and emits exactly one solver constraint
    per consecutive pair, so counting off each path's edge count recovers the
    per-clue grouping without depending on variable names.
    """
    address_of = _cell_addresses(engine)
    edges = _strict_less_pairs(engine)
    grouped: list[list[tuple[str, str]]] = []
    cursor = 0
    for clue in engine.constraints_of("thermo"):
        edge_count = len(cast("list[str]", clue.params["path"])) - 1
        clue_edges = edges[cursor : cursor + edge_count]
        grouped.append([(address_of[a], address_of[b]) for a, b in clue_edges])
        cursor += edge_count
    return grouped


def distinct_count_targets(engine: Engine) -> dict[str, int]:
    """Every counting rule, as its label mapped to the number of distinct
    digits it demands.

    One counting rule costs O(cells x digits) solver constraints, and only one
    states the count: the sum over its per-digit markers. The label is a naming
    convention (`<label>.present<digit>`), so it is the one thing here read off
    a variable's name.

    A pair-difference clue's `d == k` pin is, structurally, the same shape as
    this sum — a single-var linear equality over a non-content var — so its
    target var is excluded by role (`_abs_equality_targets`) rather than by
    name: a difference target is never a counting total.
    """
    address_of = _cell_addresses(engine)
    abs_targets = set(_abs_equality_targets(engine))
    names = engine.model.proto.variables
    targets: dict[str, int] = {}
    for variables, total in _sums(engine):
        if any(variable in address_of for variable in variables):
            continue
        if any(variable in abs_targets for variable in variables):
            continue
        label = names[variables[0]].name.rsplit(".", 1)[0]
        # A label names a rule, so a repeat would silently drop one from the
        # answer. Say so instead.
        assert label not in targets, f"two counting rules are labelled {label!r}"
        targets[label] = total
    return targets
