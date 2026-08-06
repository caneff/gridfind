"""The working-state reader: header line, RxCy addressing, given/candidate/place.

This is the shared-core half of the working-state grammar (spec #4, decision
12) — the directives every grid puzzle understands, regardless of which
layers are active.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridfind.engine import Engine
from gridfind.puzzle import Candidate, Given, Place

HEADER_PREFIX = "stack:"
MIN_DIGIT = 0
MAX_DIGIT = 9

# Given/Place/Candidate are defined once in `puzzle`, reused here (issue #46).
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
    if kind in ("given", "place", "candidate"):
        if len(tokens) != 3:
            msg = f"malformed {kind!r} directive, expected 3 fields: {line!r}"
            raise ValueError(msg)
        address, rest = tokens[1], tokens[2]
        if kind == "given":
            return Given(address=address, digit=_parse_digit(rest))
        if kind == "place":
            return Place(address=address, digit=_parse_digit(rest))
        return Candidate(address=address, digits=_parse_digit_set(rest))
    msg = f"unknown working-state directive {kind!r} in line {line!r}"
    raise ValueError(msg)


def _parse_digit(text: str) -> int:
    try:
        digit = int(text)
    except ValueError as exc:
        msg = f"expected an integer digit, got {text!r}"
        raise ValueError(msg) from exc
    if not MIN_DIGIT <= digit <= MAX_DIGIT:
        msg = f"digit {digit} out of range [{MIN_DIGIT}, {MAX_DIGIT}]: {text!r}"
        raise ValueError(msg)
    return digit


def _parse_digit_set(text: str) -> frozenset[int]:
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        msg = f"expected a digit set like '{{1,2,3}}', got {text!r}"
        raise ValueError(msg)
    inner = stripped[1:-1].strip()
    if not inner:
        msg = f"candidate digit set must not be empty: {text!r}"
        raise ValueError(msg)
    digits = [_parse_digit(part.strip()) for part in inner.split(",")]
    if len(digits) != len(set(digits)):
        msg = f"candidate digit set has a duplicate digit: {text!r}"
        raise ValueError(msg)
    return frozenset(digits)


def apply(engine: Engine, working_state: WorkingState) -> None:
    """Add a rule per directive against the addressed cell's content."""
    for directive in working_state.directives:
        (var,) = engine.cells[directive.address].content
        if isinstance(directive, Given | Place):
            engine.model.add(var == directive.digit)
        else:
            allowed = [(digit,) for digit in sorted(directive.digits)]
            engine.model.add_allowed_assignments([var], allowed)
