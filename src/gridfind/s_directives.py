"""The Schrödinger working-state directive codec (issue #211, ADR-0006).

`WorkingState.s_directives` (`puzzle.py`) is a tuple of five small tagged
dataclasses — `SingletonPin`, `SCellPin`, `BareSingleton`, `BareSCell`,
`HalfSCell`. The dataclasses themselves are bare schema and stay in
`puzzle.py`; the genuine logic around them — the `kind`-tag dispatch that
reads one back from a parsed JSON object, its mirror that writes one out, and
the guard that refuses an `SCellPin` whose pair is not exactly two distinct
digits (CONTEXT.md `schrodinger` layer) — lives here, named, instead of
hiding among the plain structs.

`puzzle.py` and this module import each other: `WorkingState` calls the codec
here, and the codec constructs the dataclasses `puzzle.py` defines. Both
sides import the *module*, not names out of it, and touch the other's
attributes only inside function bodies — never at module load time — so the
cycle resolves regardless of which module a caller happens to import first.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import Any

from gridfind import puzzle
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


def s_directive_to_dict(directive: puzzle.SDirective) -> dict[str, puzzle.JsonValue]:
    """One directive as a `{kind, address, …}` wire object. Every directive
    carries `kind` and `address`; a digit-bearing one adds `digit`, and an
    S-cell pin adds its `pair` as a sorted two-element list (mirroring
    `Candidate.digits`). The bare directives carry nothing more."""
    out: dict[str, puzzle.JsonValue] = {
        "kind": directive.kind,
        "address": directive.address,
    }
    if isinstance(directive, puzzle.SingletonPin | puzzle.HalfSCell):
        out["digit"] = directive.digit
    elif isinstance(directive, puzzle.SCellPin):
        out["pair"] = sorted(directive.pair)
    return out


@cache
def _readers() -> dict[str, Callable[[Any], puzzle.SDirective]]:
    # Built lazily (not at module load) and cached, since `puzzle` isn't fully
    # loaded yet the moment this module is; deferring the attribute access
    # into a function body is what lets the two modules import each other.
    # `d` is `Any` at the same parsed-JSON boundary `Puzzle.from_dict` narrows
    # through a local `doc: Any` — the raw dict's values are genuinely
    # untyped until a reader picks a shape for them.
    return {
        puzzle.SingletonPin.kind: (
            lambda d: puzzle.SingletonPin(address=d["address"], digit=d["digit"])
        ),
        puzzle.SCellPin.kind: (
            lambda d: puzzle.SCellPin(address=d["address"], pair=frozenset(d["pair"]))
        ),
        puzzle.BareSingleton.kind: lambda d: puzzle.BareSingleton(address=d["address"]),
        puzzle.BareSCell.kind: lambda d: puzzle.BareSCell(address=d["address"]),
        puzzle.HalfSCell.kind: (
            lambda d: puzzle.HalfSCell(address=d["address"], digit=d["digit"])
        ),
    }


# from_dict dispatches on the directive's kind tag (ADR-0006). Reading an
# S-cell pin runs SCellPin.__post_init__, so a mis-sized pair in a save raises
# MalformedPuzzleError here — a malformed pin never reaches memory. An unknown
# kind is a structurally broken save, so the missing entry raises an ordinary
# KeyError, not MalformedPuzzleError, which is reserved for bad content.
def s_directive_from_dict(data: dict[str, puzzle.JsonValue]) -> puzzle.SDirective:
    kind = data["kind"]
    if not isinstance(kind, str):
        msg = f"s_directive 'kind' must be a string, got {kind!r}"
        raise TypeError(msg)
    return _readers()[kind](data)
