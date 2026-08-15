"""The structured puzzle input: `Puzzle` + `WorkingState`, JSON round-tripping.

gridfind's one user-facing input is a `Puzzle` (the setter's definition: a
board, a list of typed constraints, and the givens) paired with a
`WorkingState` (the solver's evolving placements and candidates). Both are
frozen dataclasses that serialize to JSON and read back to an *equal* object — JSON is
the one durable on-disk form.

This module is schema only: nothing here calls `verdict` or builds a model.
It reaches into `gridfind.engine` for `MalformedPuzzleError` itself — the
shared refusal for a document that is not a well-formed puzzle,
so a caller catches one class regardless of which module noticed — and into
`gridfind.s_directives` for the Schrödinger directive codec and pair guard:
the five directive dataclasses below are bare schema, but
reading/writing them and validating an S-cell pin's pair is real logic named
in its own module, not hidden here among the plain structs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar

from gridfind import s_directives
from gridfind.engine import MalformedPuzzleError

# A JSON scalar/array/object value — the genuine open boundary a constraint's
# params live at (a killer sum is an int, a thermo path is a list).
JsonValue = object

# "no values given, derive them from size" — matched by identity, so it is
# this one object and not merely any empty range. A sentinel rather than
# `None` keeps `Board.values` a plain `range` for every reader, instead of a
# `range | None` each one has to narrow.
_UNSET_VALUES = range(0)

# A serialized non-default `values` is [start, stop, step].
_RANGE_PARTS = 3


def _values_from_size(size: int) -> range:
    """The digit values a board of this size holds unless told otherwise."""
    return range(1, size + 1)


@dataclass(frozen=True)
class Board:
    """The grid the puzzle is played on: its size, and the digit values a cell
    may hold. `values` is a `range` so one object serves every
    consumer — bounds via its ends, the digit set via iteration, membership
    via `in`. It is a real field, not a derived one: a setter may hand in
    values decoupled from size (an offset, a non-1 start), and only leaving
    them out falls back to `range(1, size + 1)`. An empty range is refused —
    a board whose cells may hold nothing is not a board.

    On the wire, values that differ from that default serialize as the
    `[start, stop, step]` triple `range(*...)` reads back — so a board is
    equal to itself across a round-trip whatever its values, while a board
    that took the default writes no `values` key at all.
    """

    size: int
    values: range = _UNSET_VALUES

    def __post_init__(self) -> None:
        if self.values is _UNSET_VALUES:
            object.__setattr__(self, "values", _values_from_size(self.size))
        elif not self.values:
            msg = f"a board's values must be a non-empty range, got {self.values!r}"
            raise MalformedPuzzleError(msg)


@dataclass(frozen=True)
class Given:
    """A setter's fixed clue: a digit pinned at a cell."""

    address: str
    digit: int


@dataclass(frozen=True)
class Placement:
    """A digit a solver has placed at a cell, as part of the hand-solve."""

    address: str
    digit: int


@dataclass(frozen=True)
class Candidate:
    """A cell a solver has narrowed to a subset of digits, without placing."""

    address: str
    digits: frozenset[int]


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
        s_directives.validate_s_cell_pair(self.pair)


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


@dataclass(frozen=True)
class ModifierDirective:
    """A discovered-modifier working-state directive: this cell either **is**
    or **is not** a discovered modifier. Its own
    channel on `WorkingState`, mirroring `s_directives` (ADR-0006) rather than
    folding into `given`/`candidate`/`placement` — a modifier's position is
    discovered, not a digit fact those channels state. Unlike a Schrödinger
    directive it carries no digit or pair, since `is_modifier` is a bare
    per-cell boolean; one shape covers both states, so no `kind`-tagged union
    is needed here."""

    address: str
    is_modifier: bool


@dataclass(frozen=True)
class Constraint:
    """One typed statement a setter makes — a bare `{type}`, or a type carrying
    its own params (a killer cage's cells and sum, a thermo path). Many
    constraints per variant: two X clues are two constraints of one variant.
    The shape is open so a future data-bearing variant adds no new grammar.
    """

    type: str
    # dict makes Constraint unhashable, but only equality is compared, which
    # dicts do fine.
    params: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class Puzzle:
    """The setter's definition: a board, typed constraints, and givens."""

    board: Board
    constraints: tuple[Constraint, ...] = ()
    givens: tuple[Given, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            {
                "board": _board_to_dict(self.board),
                "constraints": [{"type": c.type, **c.params} for c in self.constraints],
                "givens": [
                    {"address": g.address, "digit": g.digit} for g in self.givens
                ],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> Puzzle:
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_dict(cls, data: dict[str, JsonValue]) -> Puzzle:
        """Read a Puzzle from an already-parsed JSON object — the seam a caller
        holding the whole document uses, so it reads a sub-object without
        re-serializing it for `from_json` to parse again."""
        doc: Any = data  # parsed-JSON boundary, narrowed by the typed helpers
        return cls(
            board=_board_from_dict(doc["board"]),
            constraints=tuple(_constraint_from_dict(c) for c in doc["constraints"]),
            givens=tuple(
                Given(address=g["address"], digit=g["digit"]) for g in doc["givens"]
            ),
        )


@dataclass(frozen=True)
class WorkingState:
    """The solver's evolving marks: placements, candidates, the Schrödinger
    directives (ADR-0006), and the discovered-modifier directives. Defaults to
    EMPTY. `places` keeps the wire key's spelling; `s_directives` is one
    tagged list, not a field per directive kind; `modifier_directives` is its
    own sibling channel, one shape per entry, not folded into
    given/candidate/placement."""

    places: tuple[Placement, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    s_directives: tuple[SDirective, ...] = ()
    modifier_directives: tuple[ModifierDirective, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            {
                "places": [
                    {"address": p.address, "digit": p.digit} for p in self.places
                ],
                "candidates": [
                    {"address": c.address, "digits": sorted(c.digits)}
                    for c in self.candidates
                ],
                "s_directives": [
                    s_directives.s_directive_to_dict(d) for d in self.s_directives
                ],
                "modifier_directives": [
                    {"address": d.address, "is_modifier": d.is_modifier}
                    for d in self.modifier_directives
                ],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> WorkingState:
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_dict(cls, data: dict[str, JsonValue]) -> WorkingState:
        """Read a WorkingState from an already-parsed JSON object — the seam a
        caller holding the whole document uses (see `Puzzle.from_dict`)."""
        doc: Any = data  # parsed-JSON boundary, narrowed by the typed helpers
        return cls(
            places=tuple(
                Placement(address=p["address"], digit=p["digit"]) for p in doc["places"]
            ),
            candidates=tuple(
                Candidate(address=c["address"], digits=frozenset(c["digits"]))
                for c in doc["candidates"]
            ),
            # A save with no s_directives key predates the grammar — read it as
            # an empty tuple rather than refusing it (ADR-0006).
            s_directives=tuple(
                s_directives.s_directive_from_dict(d)
                for d in doc.get("s_directives", [])
            ),
            # Same empty-default treatment for a save that predates the
            # modifier channel.
            modifier_directives=tuple(
                ModifierDirective(address=d["address"], is_modifier=d["is_modifier"])
                for d in doc.get("modifier_directives", [])
            ),
        )


EMPTY = WorkingState()


def _board_to_dict(board: Board) -> dict[str, JsonValue]:
    if board.values == _values_from_size(board.size):
        return {"size": board.size}
    values = [board.values.start, board.values.stop, board.values.step]
    return {"size": board.size, "values": values}


def _board_from_dict(data: dict[str, JsonValue]) -> Board:
    size = data["size"]
    if not isinstance(size, int):
        msg = f"board 'size' must be an int, got {size!r}"
        raise MalformedPuzzleError(msg)
    if "values" not in data:
        return Board(size=size)
    values = data["values"]
    if not isinstance(values, list) or len(values) != _RANGE_PARTS:
        msg = f"board 'values' must be a [start, stop, step] list, got {values!r}"
        raise MalformedPuzzleError(msg)
    start, stop, step = values
    if not (isinstance(start, int) and isinstance(stop, int) and isinstance(step, int)):
        msg = f"board 'values' must be three ints, got {values!r}"
        raise MalformedPuzzleError(msg)
    return Board(size=size, values=range(start, stop, step))


def _constraint_from_dict(data: dict[str, JsonValue]) -> Constraint:
    kind = data["type"]
    if not isinstance(kind, str):
        msg = f"constraint 'type' must be a string, got {kind!r}"
        raise MalformedPuzzleError(msg)
    params = {key: value for key, value in data.items() if key != "type"}
    return Constraint(type=kind, params=params)
