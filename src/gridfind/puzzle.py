"""The structured puzzle input: `Puzzle` + `WorkingState`, JSON round-tripping.

gridfind's one user-facing input is a `Puzzle` (the setter's definition: a
board, a list of typed constraints, and the givens) paired with a
`WorkingState` (the solver's evolving placements and candidates). Both are
frozen dataclasses that serialize to JSON and read back to an *equal* object — JSON is
the one durable on-disk form (spec #45, issue #46).

This module is schema only: nothing here calls `verdict` or builds a model.
The one thing it reaches into `gridfind.engine` for is `MalformedPuzzleError`
itself — the shared refusal for a document that is not a well-formed puzzle
(issue #107), so a caller catches one class regardless of which module
noticed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from gridfind.engine import MalformedPuzzleError

# A JSON scalar/array/object value — the genuine open boundary a constraint's
# params live at (a killer sum is an int, a thermo path is a list).
JsonValue = object

# "no values given, derive them from size" — matched by identity, so it is
# this one object and not merely any empty range. A sentinel rather than
# `None` keeps `Board.values` a plain `range` for every reader, instead of a
# `range | None` each one has to narrow (issue #91).
_UNSET_VALUES = range(0)

# A serialized non-default `values` is [start, stop, step].
_RANGE_PARTS = 3


def _values_from_size(size: int) -> range:
    """The digit values a board of this size holds unless told otherwise."""
    return range(1, size + 1)


@dataclass(frozen=True)
class Board:
    """The grid the puzzle is played on: its size, and the digit values a cell
    may hold (issue #77). `values` is a `range` so one object serves every
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
class Constraint:
    """One typed statement a setter makes — a bare `{type}`, or a type carrying
    its own params (a killer cage's cells and sum, a thermo path). Many
    constraints per variant: two X clues are two constraints of one variant.
    The shape is open so a future data-bearing variant adds no new grammar.
    """

    type: str
    # ponytail: dict makes Constraint unhashable; #47 needs canonical identity
    # and will freeze params then. #46 only compares equality, which dicts do
    # fine.
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
        data = json.loads(text)
        return cls(
            board=_board_from_dict(data["board"]),
            constraints=tuple(_constraint_from_dict(c) for c in data["constraints"]),
            givens=tuple(
                Given(address=g["address"], digit=g["digit"]) for g in data["givens"]
            ),
        )


@dataclass(frozen=True)
class WorkingState:
    """The solver's evolving marks: placements and candidates. Defaults to
    EMPTY. The field keeps the wire key's spelling, `places`."""

    places: tuple[Placement, ...] = ()
    candidates: tuple[Candidate, ...] = ()

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
            }
        )

    @classmethod
    def from_json(cls, text: str) -> WorkingState:
        data = json.loads(text)
        return cls(
            places=tuple(
                Placement(address=p["address"], digit=p["digit"])
                for p in data["places"]
            ),
            candidates=tuple(
                Candidate(address=c["address"], digits=frozenset(c["digits"]))
                for c in data["candidates"]
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
