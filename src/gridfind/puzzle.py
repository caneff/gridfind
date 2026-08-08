"""The structured puzzle input: `Puzzle` + `WorkingState`, JSON round-tripping.

gridfind's one user-facing input is a `Puzzle` (the setter's definition: a
board, a list of typed variant records, and the givens) paired with a
`WorkingState` (the solver's evolving places and candidates). Both are frozen
dataclasses that serialize to JSON and read back to an *equal* object — JSON is
the one durable on-disk form (spec #45, issue #46).

This module is schema only: nothing here calls `verdict` or touches the engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

# A JSON scalar/array/object value — the genuine open boundary a variant
# record's params live at (a killer sum is an int, a thermo path is a list).
JsonValue = object


@dataclass(frozen=True)
class Board:
    """The grid the puzzle is played on: its size, and the digit domain that
    size implies (issue #77). `domain` is a `range` so one object serves
    every consumer — bounds via its ends, the digit set via iteration,
    membership via `in`. A domain decoupled from size (an offset, a non-1
    start) would be a matter of setting a different range; the plumbing to
    pass one in isn't built yet, so `domain` always derives from `size`.
    """

    size: int
    domain: range = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", range(1, self.size + 1))


@dataclass(frozen=True)
class Given:
    """A setter's fixed clue: a digit pinned at a cell."""

    address: str
    digit: int


@dataclass(frozen=True)
class Place:
    """A digit a solver has placed at a cell, as part of the hand-solve."""

    address: str
    digit: int


@dataclass(frozen=True)
class Candidate:
    """A cell a solver has narrowed to a subset of digits, without placing."""

    address: str
    digits: frozenset[int]


@dataclass(frozen=True)
class Variant:
    """A typed rule record — a bare `{type}`, or a type carrying its own params
    (a killer cage's cells and sum, a thermo path). The record shape is open so
    a future data-bearing variant adds no new grammar.
    """

    type: str
    # ponytail: dict makes Variant unhashable; #47 needs canonical identity and
    # will freeze params then. #46 only compares equality, which dicts do fine.
    params: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class Puzzle:
    """The setter's definition: a board, typed variant records, and givens."""

    board: Board
    variants: tuple[Variant, ...] = ()
    givens: tuple[Given, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            {
                "board": {"size": self.board.size},
                "variants": [{"type": v.type, **v.params} for v in self.variants],
                "givens": [
                    {"address": g.address, "digit": g.digit} for g in self.givens
                ],
            }
        )

    @classmethod
    def from_json(cls, text: str) -> Puzzle:
        data = json.loads(text)
        return cls(
            board=Board(size=data["board"]["size"]),
            variants=tuple(_variant_from_dict(v) for v in data["variants"]),
            givens=tuple(
                Given(address=g["address"], digit=g["digit"]) for g in data["givens"]
            ),
        )


@dataclass(frozen=True)
class WorkingState:
    """The solver's evolving marks: places and candidates. Defaults to EMPTY."""

    places: tuple[Place, ...] = ()
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
                Place(address=p["address"], digit=p["digit"]) for p in data["places"]
            ),
            candidates=tuple(
                Candidate(address=c["address"], digits=frozenset(c["digits"]))
                for c in data["candidates"]
            ),
        )


EMPTY = WorkingState()


def _variant_from_dict(data: dict[str, JsonValue]) -> Variant:
    kind = data["type"]
    if not isinstance(kind, str):
        msg = f"variant record 'type' must be a string, got {kind!r}"
        raise ValueError(msg)
    params = {key: value for key, value in data.items() if key != "type"}
    return Variant(type=kind, params=params)
