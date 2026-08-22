"""The Schrödinger working-state directives: dataclasses, closed union, and
wire codec — one home for all six (ADR-0006).

`WorkingState.s_directives` (`puzzle.py`) is a tuple of six small tagged
dataclasses — `SingletonPin`, `SCellPin`, `BareSingleton`, `BareSCell`,
`HalfSCell`, `SCellMarkRestriction`. Everything about them lives here: the
dataclasses, the closed `SDirective` union, the `kind`-tag dispatch that reads
one back from a parsed JSON object, its mirror that writes one out, and the
guard that refuses an `SCellPin` whose pair is not exactly two distinct
digits (CONTEXT.md `schrodinger` layer). `puzzle.py`'s `WorkingState` imports
this module for the `SDirective` type and calls the codec from its own
`to_json`/`from_json`; nothing here imports `puzzle`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, assert_never

from gridfind.engine import MalformedPuzzleError

# An S-cell holds a pair — one digit is no pair, three cannot be one.
_S_CELL_PAIR_SIZE = 2


def validate_s_cell_pair(pair: frozenset[int]) -> None:
    """Refuse a pair that is not exactly two distinct digits (ADR-0006). Called
    from `SCellPin.__post_init__`, counted after the frozenset collapses
    duplicates, so a malformed S-cell pin can never exist in memory."""
    if len(pair) != _S_CELL_PAIR_SIZE:
        msg = f"an S-cell pin's pair must be two distinct digits, got {sorted(pair)}"
        raise MalformedPuzzleError(msg)


@dataclass(frozen=True)
class SingletonPin:
    """A Schrödinger directive: this cell is a **singleton** holding `digit` —
    not an S-cell (CONTEXT.md `schrodinger`). The Schrödinger analog of a
    settled given or placement alike — under a `schrodinger` layer both carry
    the extra "not an S-cell" claim (`is_s == 0`). `kind` is the wire tag
    `to_json`/`from_json` dispatch on (ADR-0006)."""

    address: str
    digit: int
    kind: ClassVar[str] = "singleton-pin"


@dataclass(frozen=True)
class SCellPin:
    """A Schrödinger directive: this cell **is** an S-cell holding the pair
    `{a, b}` (CONTEXT.md `schrodinger`). The pair mirrors `Candidate.digits` as
    a `frozenset[int]`. Its shape is guarded here at construction so a malformed
    S-cell pin can never exist in memory (ADR-0006): the pair must be exactly
    two distinct digits, counted after the frozenset collapses duplicates."""

    address: str
    pair: frozenset[int]
    kind: ClassVar[str] = "s-cell-pin"

    def __post_init__(self) -> None:
        validate_s_cell_pair(self.pair)


@dataclass(frozen=True)
class BareSingleton:
    """A Schrödinger directive: this cell **is a singleton** (not an S-cell),
    digit unstated (CONTEXT.md `schrodinger`). A singleton pin minus its
    digit — it fixes S-cell-ness, leaves the digit free."""

    address: str
    kind: ClassVar[str] = "bare-singleton"


@dataclass(frozen=True)
class BareSCell:
    """A Schrödinger directive: this cell **is an S-cell**, both digits unstated
    (CONTEXT.md `schrodinger`). An S-cell pin minus its pair."""

    address: str
    kind: ClassVar[str] = "bare-s-cell"


@dataclass(frozen=True)
class HalfSCell:
    """A Schrödinger directive: this cell **is an S-cell** and `digit` is one of
    its two digits, partner unstated (CONTEXT.md `schrodinger`) — a reified
    "digit appears among the two slots" claim, between an S-cell pin and a bare
    S-cell."""

    address: str
    digit: int
    kind: ClassVar[str] = "half-s-cell"


@dataclass(frozen=True)
class SCellMarkRestriction:
    """A Schrödinger directive: a caged S-cell's center marks, layered as a
    consistency restriction over the cage's own directive (CONTEXT.md
    `schrodinger`). Every one of the cell's real slots must draw from `digits`.
    It never selects the S-cell — the cage's `value` does that — so it only
    tightens the cage-chosen pin/half/bare or, when the marks cannot hold the
    directive's pair, makes the model infeasible → broke. Present only when the
    caged cell carries center marks, which are optional."""

    address: str
    digits: frozenset[int]
    kind: ClassVar[str] = "s-cell-mark-restriction"


# The Schrödinger working-state directives, hard-coded not registered
# (ADR-0006). A closed union: a second directive-bearing layer would need its
# own seam.
SDirective = (
    SingletonPin
    | SCellPin
    | BareSingleton
    | BareSCell
    | HalfSCell
    | SCellMarkRestriction
)


def s_directive_to_dict(directive: SDirective) -> dict[str, object]:
    """One directive as a `{kind, address, …}` wire object. Every directive
    carries `kind` and `address`; a digit-bearing one adds `digit`, and an
    S-cell pin adds its `pair` as a sorted two-element list (mirroring
    `Candidate.digits`). The bare directives carry nothing more."""
    out: dict[str, object] = {
        "kind": directive.kind,
        "address": directive.address,
    }
    if isinstance(directive, SingletonPin | HalfSCell):
        out["digit"] = directive.digit
    elif isinstance(directive, SCellPin):
        out["pair"] = sorted(directive.pair)
    elif isinstance(directive, SCellMarkRestriction):
        out["digits"] = sorted(directive.digits)
    elif isinstance(directive, BareSingleton | BareSCell):
        pass
    else:
        assert_never(directive)
    return out


# The parsed-JSON boundary a reader narrows is genuinely untyped (`d: Any`)
# until it picks a shape for the values.
_READERS: dict[str, Callable[[Any], SDirective]] = {
    SingletonPin.kind: (lambda d: SingletonPin(address=d["address"], digit=d["digit"])),
    SCellPin.kind: (
        lambda d: SCellPin(address=d["address"], pair=frozenset(d["pair"]))
    ),
    BareSingleton.kind: lambda d: BareSingleton(address=d["address"]),
    BareSCell.kind: lambda d: BareSCell(address=d["address"]),
    HalfSCell.kind: (lambda d: HalfSCell(address=d["address"], digit=d["digit"])),
    SCellMarkRestriction.kind: (
        lambda d: SCellMarkRestriction(
            address=d["address"], digits=frozenset(d["digits"])
        )
    ),
}


def s_directive_from_dict(data: dict[str, object]) -> SDirective:
    """Read one Schrödinger directive back from its `{kind, address, …}` wire
    object, dispatching on `kind` (ADR-0006). Reading an S-cell pin runs
    `SCellPin.__post_init__`, so a mis-sized pair in a save raises
    `MalformedPuzzleError` here — a malformed pin never reaches memory. An
    unknown `kind` is a structurally broken save, so the missing entry raises
    an ordinary `KeyError`, not `MalformedPuzzleError`, which is reserved for
    bad content."""
    kind = data["kind"]
    if not isinstance(kind, str):
        msg = f"s_directive 'kind' must be a string, got {kind!r}"
        raise TypeError(msg)
    return _READERS[kind](data)
