"""The read side of `emit`, shared by the layers package's tests.

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
    home for decoding a cell's solver domain.

    Not the declared value set itself: a stepped `Board.values`
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


def sum_rules(engine: Engine) -> list[tuple[list[str], int]]:
    """Every sum-over-cells rule, as the addresses it adds up and the total
    they must reach. A sum over cell content is this rule; a counting rule
    sums per-digit markers instead."""
    address_of = _cell_addresses(engine)
    return [
        ([address_of[variable] for variable in variables], total)
        for variables, total in _sums(engine)
        if all(variable in address_of for variable in variables)
    ]


def _less_pairs(engine: Engine, *, closed_at: int) -> list[tuple[int, int]]:
    """Every `a < b` (`closed_at=-1`) or `a <= b` (`closed_at=0`) solver
    constraint, as its two operand variable indices, in emission order.

    Read structurally off the compiled linear form CP-SAT's `add(a < b)` /
    `add(a <= b)` produces: two vars with coefficients `[1, -1]` and a domain
    closed at `-1` (`a - b <= -1`, strict) or `0` (`a - b <= 0`, non-strict,
    a slow thermo edge) — distinct in shape from a plain sum's `[1, 1]`
    coefficients and single-value domain (`_sums`), and from `add_abs_equality`'s
    `lin_max` form (`_abs_equality_targets`); `closed_at` is the one bit that
    tells a slow edge from a normal one, never variable names.
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
        if list(lin.coeffs) == [1, -1] and domain[-1:] == [closed_at]:
            pairs.append((variables[0], variables[1]))
    return pairs


def thermo_rules(engine: Engine) -> list[list[tuple[str, str]]]:
    """Every thermo rule, grouped by clue, as each consecutive pair's
    addresses in path order.

    Reads the strict (`_less_pairs(closed_at=-1)`) and non-strict
    (`_less_pairs(closed_at=0)`) edge streams structurally, then regroups by
    each clue's own path length and `slow` flag in emission order —
    `Thermo.emit` walks `constraints_of` in order and emits exactly one
    solver constraint per consecutive pair, into whichever stream its `slow`
    flag picks, so counting off each path's edge count against the matching
    stream recovers the per-clue grouping without depending on variable
    names.
    """
    address_of = _cell_addresses(engine)
    strict_edges = _less_pairs(engine, closed_at=-1)
    slow_edges = _less_pairs(engine, closed_at=0)
    grouped: list[list[tuple[str, str]]] = []
    strict_cursor = 0
    slow_cursor = 0
    for clue in engine.constraints_of("thermo"):
        edge_count = len(cast("list[str]", clue.params["path"])) - 1
        if cast("bool", clue.params["slow"]):
            clue_edges = slow_edges[slow_cursor : slow_cursor + edge_count]
            slow_cursor += edge_count
        else:
            clue_edges = strict_edges[strict_cursor : strict_cursor + edge_count]
            strict_cursor += edge_count
        grouped.append([(address_of[a], address_of[b]) for a, b in clue_edges])
    return grouped


def indexing_rules(engine: Engine) -> list[tuple[str, int, list[str]]]:
    """Every indexing rule, as `(control address, coordinate, line)` — the
    control cell's own address, the coordinate its `add_element` pins the
    line's selected cell to, and the indexed line's cell addresses in
    position order (`1..N`).

    Reads the `element` proto `Indexing.emit` produces structurally: the
    index expression's sole var is the control's `d0` (its `-1` offset is
    the involution's own bookkeeping, not read here), the target expression's
    constant offset is the coordinate (a plain int, never a var, since
    `Indexing` pins it directly), and each `exprs` entry's sole var is one
    line cell's `d0`, in emission order. Matched back to each clue's marked
    cells by the control var, so the return order follows
    `engine.constraints_of(\"indexing\")` and each clue's own `cells` order,
    not the model's constraint-emission order.
    """
    address_of = _cell_addresses(engine)
    by_control_var: dict[int, tuple[int, list[str]]] = {}
    for constraint in engine.model.proto.constraints:
        if not constraint.has_element():
            continue
        element = constraint.element
        control_var = element.linear_index.vars[0]
        coordinate = element.linear_target.offset
        line = [address_of[expr.vars[0]] for expr in element.exprs]
        by_control_var[control_var] = (coordinate, line)
    rules: list[tuple[str, int, list[str]]] = []
    for clue in engine.constraints_of("indexing"):
        for address in cast("list[str]", clue.params["cells"]):
            coordinate, line = by_control_var[engine.d0(address).index]
            rules.append((address, coordinate, line))
    return rules


def numbered_rooms_rules(engine: Engine) -> list[tuple[str, str, list[str]]]:
    """Every numbered-rooms rule, as `(outside address, near-cell address,
    line)` — the outside cell `add_element`'s target names, the line's own
    near cell (`line[0]`) whose digit `add_element`'s index reads, and the
    line addresses in emission order.

    Reads the `element` proto `NumberedRooms.emit` produces structurally,
    mirroring `indexing_rules`: the index expression's sole var is the near
    cell's `d0` (its `-1` offset is the involution's own bookkeeping, not
    read here). Unlike `indexing_rules`'s fixed-int coordinate, the target
    here is itself a variable — the outside cell's own `d0`, not a plain
    int — so it is read as `linear_target.vars[0]` rather than `.offset`.
    """
    address_of = _cell_addresses(engine)
    by_index_var: dict[int, tuple[int, list[str]]] = {}
    for constraint in engine.model.proto.constraints:
        if not constraint.has_element():
            continue
        element = constraint.element
        index_var = element.linear_index.vars[0]
        target_var = element.linear_target.vars[0]
        line = [address_of[expr.vars[0]] for expr in element.exprs]
        by_index_var[index_var] = (target_var, line)
    rules: list[tuple[str, str, list[str]]] = []
    for clue in engine.constraints_of("numbered-rooms"):
        cells = cast("list[str]", clue.params["cells"])
        outside, near = cells[0], cells[1]
        target_var, line = by_index_var[engine.d0(near).index]
        assert address_of[target_var] == outside
        rules.append((outside, near, line))
    return rules


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
