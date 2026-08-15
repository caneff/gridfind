"""The working-state applier: turns a `Puzzle`'s givens and a `WorkingState`'s
marks into restrictions on an already-built engine model.

These functions never observe the solve — they only narrow the model before it
runs. `apply` is the one entry point.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from ortools.sat.python import cp_model

from gridfind.engine import Engine, MalformedPuzzleError
from gridfind.puzzle import ModifierDirective, Placement, Puzzle, WorkingState
from gridfind.s_directives import (
    BareSCell,
    BareSingleton,
    HalfSCell,
    SCellMarkRestriction,
    SDirective,
    SingletonPin,
)


class _AddressedDirective(Protocol):
    """The one shape `_apply_directives` needs from a directive: an address
    to run the off-board `contents` guard on. A property getter, not a plain
    attribute — every directive dataclass is frozen, so a plain attribute
    member (which Protocol treats as read/write) would reject them all."""

    @property
    def address(self) -> str: ...


def apply(engine: Engine, puzzle: Puzzle, working_state: WorkingState) -> None:
    """Fix the model from the puzzle's givens and the working state's marks
    and Schrödinger directives. A given stays literal to the cell's base slot
    (`d0 = d`) and a candidate restricts a cell to a digit subset — both go
    through the engine's one `restrict` call. A placement
    diverges: it refines to `d ∈ content`, so it survives a
    digit landing on a Schrödinger S-cell's upper half — see
    `_apply_placement`. Directives apply last, restricting the two axes
    `engine.restrict` can't reach (S-cell-ness and the second content slot)
    — see `_apply_s_directives`. Declared-modifier directives (a doubler's red
    bit) apply last of all, pinning the modifier layer's `is_modifier` — see
    `_apply_modifier_directives`."""
    for given in puzzle.givens:
        engine.restrict(given.address, {given.digit})
    for placement in working_state.places:
        _apply_placement(engine, placement)
    for candidate in working_state.candidates:
        engine.restrict(candidate.address, candidate.digits)
    _apply_s_directives(engine, working_state.s_directives)
    _apply_modifier_directives(engine, working_state.modifier_directives)


def _apply_placement(engine: Engine, placement: Placement) -> None:
    """A placement fixes digit ∈ content — either slot — rather than `given`'s
    literal d0 = d. On an
    ordinary board `content` is length 1, so this collapses to exactly the
    same `d0 == d` a given states; on a Schrödinger board it also honors a
    placement that a solve later reveals as an S-cell's upper half. Reuses
    the same reified-holds OR idiom the half-S-cell directive uses —
    `engine.reify_holds` over `engine.contents(address)` — rather than
    hand-rolling the membership OR. No `is_s` gate needed: the schrodinger
    layer's per-cell sentinel already makes `d1 == d` unsatisfiable for a
    singleton, so the OR collapses on its own."""
    address, digit = placement.address, placement.digit
    content = engine.contents(address)  # off-board raises here
    _require_in_domain(engine, address, (digit,))
    holds = engine.reify_holds(content, digit, f"placement.{address}")
    engine.model.add_bool_or(holds)


def _apply_directives[Directive: _AddressedDirective](
    engine: Engine,
    directives: Sequence[Directive],
    *,
    channel: Callable[[Engine], dict[str, cp_model.IntVar] | None],
    missing_msg: str,
    apply_one: Callable[
        [Engine, dict[str, cp_model.IntVar], Directive, list[cp_model.IntVar]], None
    ],
) -> None:
    """The shared skeleton every directive family runs: skip when there are no
    directives, raise `missing_msg` when the layer `channel` reads is absent,
    then walk the directives applying each through `apply_one` — the one home
    for the empty-check, the missing-layer guard, and the off-board `contents`
    guard every family shares. `apply_one` gets the resolved channel (never
    None) and the directive's own content slots; the per-directive model work
    stays with the caller, since that's where the families genuinely differ."""
    if not directives:
        return
    values = channel(engine)
    if values is None:
        raise MalformedPuzzleError(missing_msg)
    for directive in directives:
        content = engine.contents(directive.address)  # off-board raises here
        apply_one(engine, values, directive, content)


def _apply_s_directives(engine: Engine, directives: tuple[SDirective, ...]) -> None:
    """Apply the Schrödinger directives by restricting the already-built model
    along the two axes `engine.restrict` can't reach: S-cell-ness (`is_s`) and
    the second content slot (`d1`). Each pin/bare/half names a point on those
    axes; the mark restriction instead narrows both slots, layering over
    whichever point the cage already named:

    - singleton pin  — fix d0 to the digit, force is_s false.
    - S-cell pin     — fix both slots to the sorted pair, force is_s true.
    - bare singleton — force is_s false, digit free.
    - bare S-cell    — force is_s true, digits free.
    - half S-cell    — force is_s true and the digit into *either* slot, its
                       partner free (`digit in content`, an OR over the slots'
                       reified holds, which `engine.reify_holds` builds).
    - mark restriction — narrow *every* content slot to the caged cell's center
                       marks. It layers over the cage's own directive rather
                       than choosing one; the schrodinger layer's d0 < d1 then
                       makes a half/bare with fewer than two marks infeasible,
                       and a pin whose pair escapes the marks infeasible. Marks
                       ride in from the domain bitmask, so all are in-domain —
                       no digit guard needed.

    A consistent directive narrows the model and is honored; a contradictory
    one makes it infeasible, which the solver reports as broke.

    Two content errors are malformed, refused here before the solve:
    a directive naming a digit off the board (singleton/half/S-cell pin), and
    *any* directive on a stack with no schrodinger layer to honor it — both
    enforced by the shared `_apply_directives` skeleton, which runs the
    missing-layer check before the per-directive loop reaches a digit."""
    _apply_directives(
        engine,
        directives,
        channel=Engine.is_s,
        missing_msg=(
            "a Schrödinger pin needs a schrodinger layer, but the stack has none"
        ),
        apply_one=_apply_one_s_directive,
    )


def _apply_one_s_directive(
    engine: Engine,
    is_s: dict[str, cp_model.IntVar],
    directive: SDirective,
    content: list[cp_model.IntVar],
) -> None:
    address = directive.address
    if isinstance(directive, SingletonPin):
        _require_in_domain(engine, address, (directive.digit,))
        engine.model.add(content[0] == directive.digit)
        engine.model.add(is_s[address] == 0)
    elif isinstance(directive, BareSingleton):
        engine.model.add(is_s[address] == 0)
    elif isinstance(directive, BareSCell):
        engine.model.add(is_s[address] == 1)
    elif isinstance(directive, HalfSCell):
        _require_in_domain(engine, address, (directive.digit,))
        holds = engine.reify_holds(content, directive.digit, f"half.{address}")
        engine.model.add_bool_or(holds)
        engine.model.add(is_s[address] == 1)
    elif isinstance(directive, SCellMarkRestriction):
        allowed = [(digit,) for digit in sorted(directive.digits)]
        for slot in content:
            engine.model.add_allowed_assignments([slot], allowed)
    else:
        low, high = sorted(directive.pair)
        _require_in_domain(engine, address, (low, high))
        engine.model.add(content[0] == low)
        engine.model.add(content[1] == high)
        engine.model.add(is_s[address] == 1)


def _apply_modifier_directives(
    engine: Engine, directives: tuple[ModifierDirective, ...]
) -> None:
    """Apply the declared-modifier directives (a doubler read off a link's red
    bit) by pinning `is_modifier` — the free per-cell boolean the modifier
    layer discovers. Each directive fixes one cell to modifier or not; the
    layer's one-per-house and distinct-digit transversal then verify the
    declared set, so an ill-placed declaration solves to broke.

    Mirrors `_apply_s_directives`: the shared `_apply_directives` skeleton
    refuses a directive on a stack with no modifier layer to honor it, and
    raises through `engine.contents` on an off-board address, before the
    per-directive pin below ever runs."""
    _apply_directives(
        engine,
        directives,
        channel=Engine.is_modifier,
        missing_msg=(
            "a modifier directive needs a modifier layer, but the stack has none"
        ),
        apply_one=_apply_one_modifier_directive,
    )


def _apply_one_modifier_directive(
    engine: Engine,
    is_modifier: dict[str, cp_model.IntVar],
    directive: ModifierDirective,
    content: list[cp_model.IntVar],
) -> None:
    engine.model.add(is_modifier[directive.address] == int(directive.is_modifier))


def _require_in_domain(engine: Engine, address: str, digits: tuple[int, ...]) -> None:
    """Refuse a pin naming a digit the board never offered — the same content
    rule that governs a given or candidate (`engine.restrict`), but reaching
    both pair slots, which `restrict` (d0 only) cannot."""
    for digit in digits:
        if digit not in engine.board.values:
            values = list(engine.board.values)
            msg = f"digit {digit} is not among {values} for cell {address!r}"
            raise MalformedPuzzleError(msg)
