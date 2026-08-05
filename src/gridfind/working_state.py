"""The working-state reader: header line, RxCy addressing, given/candidate/place.

This is the shared-core half of the working-state grammar (spec #4, decision
12) — the directives every grid puzzle understands, regardless of which
layers are active.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine

HEADER_PREFIX = "stack:"


@dataclass(frozen=True)
class Given:
    """A grid cell placed to a single digit."""

    address: str
    digit: int


@dataclass(frozen=True)
class Place:
    """A digit sits at a cell, as part of the hand-solve."""

    address: str
    digit: int


@dataclass(frozen=True)
class Candidate:
    """A cell narrowed to a subset of digits, without being placed."""

    address: str
    digits: frozenset[int]


Directive = Given | Place | Candidate


@dataclass(frozen=True)
class WorkingState:
    stack: list[str]
    directives: list[Directive]


def parse(text: str) -> WorkingState:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        msg = "empty working state: expected a header line"
        raise ValueError(msg)
    header, *body = lines
    return WorkingState(
        stack=_parse_header(header),
        directives=[_parse_directive(line) for line in body],
    )


def _parse_header(line: str) -> list[str]:
    if not line.startswith(HEADER_PREFIX):
        msg = f"expected a header line starting with {HEADER_PREFIX!r}, got {line!r}"
        raise ValueError(msg)
    rest = line[len(HEADER_PREFIX) :]
    return [name.strip() for name in rest.split(",") if name.strip()]


def _parse_directive(line: str) -> Directive:
    tokens = line.split(maxsplit=2)
    kind = tokens[0]
    if kind == "given":
        address, digit = tokens[1], tokens[2]
        return Given(address=address, digit=int(digit))
    if kind == "place":
        address, digit = tokens[1], tokens[2]
        return Place(address=address, digit=int(digit))
    if kind == "candidate":
        address, digit_set = tokens[1], tokens[2]
        return Candidate(address=address, digits=_parse_digit_set(digit_set))
    msg = f"unknown working-state directive {kind!r} in line {line!r}"
    raise ValueError(msg)


def _parse_digit_set(text: str) -> frozenset[int]:
    inner = text.strip().removeprefix("{").removesuffix("}")
    return frozenset(int(part.strip()) for part in inner.split(",") if part.strip())


def apply(engine: Engine, working_state: WorkingState) -> None:
    """Add a rule per directive against the addressed cell's content."""
    for directive in working_state.directives:
        (var,) = engine.cells[directive.address].content
        if isinstance(directive, Given | Place):
            engine.model.add(var == directive.digit)
        else:
            allowed = [(digit,) for digit in sorted(directive.digits)]
            engine.model.add_allowed_assignments([var], allowed)
