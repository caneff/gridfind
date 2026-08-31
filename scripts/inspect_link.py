"""Decode SudokuMaker link(s) and report structure + verdict, in one process.

A dev tool. `gridfind <link>` already answers "does it run"; this answers the
*other* question — "what's in it, and why did it reject" — by decoding the
link, classifying each constraint the way gridfind's decode policy treats it,
and running the verdict. Many links share one OR-Tools import, so a batch costs
one startup, not one per link.

    uv run python scripts/inspect_link.py '<link>' ['<link>' ...]
    printf '%s\n' "$l1" "$l2" | uv run python scripts/inspect_link.py

Variants (doubler, S-cell) are inferred from the link's marker cages, so the
inspector takes no flags — a `--`-prefixed token is reported as unknown.
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from collections.abc import Sequence
from typing import Any, TextIO

from gridfind.engine import GridfindError
from gridfind.sudokumaker import (
    DECODER_REGISTRY,
    constraint_name,
    has_live_data,
    link_to_document,
    link_to_puzzle,
)
from gridfind.verdict import verdict

# The two wire types that describe the puzzle's structure (givens, regions)
# rather than a placeable rule — `link_to_puzzle` handles them outside the
# active/inert/disabled bucketing every other DECODER_REGISTRY row gets.
# Picked by the registry's own `name` field, so the set tracks the registry
# instead of a hand-copied `(0, 1)` nobody re-checks against it.
_STRUCTURAL_NAMES = frozenset({"givens", "regions"})
_KNOWN_TYPES = frozenset(
    wire_type
    for wire_type, decoded in DECODER_REGISTRY.items()
    if decoded.name in _STRUCTURAL_NAMES
)


def classify_constraint(constraint: dict[str, object]) -> str:
    """How gridfind's decode policy treats one constraint, for display.

    `disabled` first — the setter switched it off, so it never counts, whatever
    its type. Then the known ruleset (type 0 givens / 1 regions). Then a live
    payload marks it `active` (a real rule gridfind would have to honour); an
    enabled constraint with no such payload is `inert` (cosmetic or empty).
    """
    if constraint.get("disabled") is True:
        return "disabled"
    if constraint.get("type") in _KNOWN_TYPES:
        return "known"
    if has_live_data(constraint):
        return "active"
    return "inert"


def decode_payload(link: str) -> dict[str, object]:
    """The SudokuMaker puzzle JSON behind a `?puzzle=` link (or bare payload).

    Delegates to `link_to_document`'s boundary decode and keeps only the
    `puzzle` block — the inspector needs the dict itself to classify
    constraints, including on links `link_to_puzzle` rejects, so it can't route
    through `link_to_puzzle`'s `Puzzle`.
    """
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    data: Any = link_to_document(link)["puzzle"]
    return data


def _display_size(data: dict[str, object], cell_count: int) -> int:
    """Board edge for the report line, most specific first (`width`, then
    `size`, else `isqrt(cells)`). Display only — the verdict path sizes the
    board authoritatively via `link_to_puzzle`."""
    for key in ("width", "size"):
        value = data.get(key)
        if isinstance(value, int):
            return value
    return math.isqrt(cell_count)


def _ring_state(cells: Sequence[object], size: int) -> tuple[int, int]:
    """`(filled, total)` for the board's outer ring — row and column `0` and
    `size - 1`.

    Edge-clue puzzles (Numbered Rooms, Skyscraper) store their outside clues in
    the ring, so how much of it is filled says how much of the puzzle is spelled
    out: a full ring means every outside clue is given away. Reported, never
    judged — a link that wants all of them is legitimate.

    `(0, 0)` when the cells don't fill a square board, since `size` is a display
    guess there and the ring would be a fiction.
    """
    if size <= 0 or len(cells) != size * size:
        return 0, 0
    ring = [
        index
        for index in range(size * size)
        for row, col in [divmod(index, size)]
        if row in (0, size - 1) or col in (0, size - 1)
    ]
    return sum(1 for index in ring if cells[index]), len(ring)


def _entered(cells: Sequence[object]) -> int:
    """How many non-given cells hold a value or a pencil mark.

    A shared link is meant to open empty; anything a non-given cell carries is
    the solver's work already done for them. `probe_link` in
    sudokumaker-custom-constraints strips exactly these before a timing run,
    because the app reports a verdict "based on already entered values" instead
    of searching.
    """
    return sum(
        1 for cell in cells if isinstance(cell, dict) and cell and not cell.get("given")
    )


def _verdict_word(link: str) -> str:
    """The verdict word for a link, or `rejected (<reason>)` when the decoder
    refuses it — so one bad link reports itself instead of killing the batch.
    Variants (doubler, S-cell) are inferred from the link's marker cages, so the
    inspector needs no flags to read them."""
    try:
        puzzle, state = link_to_puzzle(link)
    except (ValueError, GridfindError) as exc:
        return f"rejected ({exc})"
    return verdict(puzzle, state).kind


def _fmt_bucket(tags: list[str]) -> str:
    """`["2000", "2000", "201"]` -> `2000x2, 201` — collapse repeats to counts."""
    return ", ".join(
        f"{tag}x{count}" if count > 1 else tag for tag, count in Counter(tags).items()
    )


def inspect_link(link: str) -> str:
    """One report line: size, givens, ring state, entered cells, the constraint
    types present, each classification bucket that isn't empty, and the
    verdict."""
    data: Any = decode_payload(link)
    cells = data.get("cells") or []
    constraints = data.get("constraints") or []

    size = _display_size(data, len(cells))
    givens = sum(1 for cell in cells if isinstance(cell, dict) and cell.get("given"))
    types = sorted({c.get("type") for c in constraints}, key=lambda t: (t is None, t))

    buckets: dict[str, list[str]] = {"active": [], "inert": [], "disabled": []}
    for constraint in constraints:
        label = classify_constraint(constraint)
        if label == "known":
            continue
        ctype = constraint.get("type")
        name = constraint_name(constraint)
        buckets[label].append(f"{ctype}({name})" if name else f"{ctype}")

    ring_filled, ring_total = _ring_state(cells, size)

    segments = [
        f"{size}x{size}",
        f"{len(cells)} cells",
        f"{givens} given{'' if givens == 1 else 's'}",
    ]
    # Dropped on a board the cells don't square up to, where the ring is a guess.
    if ring_total:
        segments.append(f"ring: {ring_filled}/{ring_total}")
    segments += [
        f"entered: {_entered(cells)}",
        "types {" + ",".join(str(t) for t in types) + "}",
    ]
    segments += [
        f"{label}: {_fmt_bucket(tags)}" for label, tags in buckets.items() if tags
    ]
    segments.append(f"verdict: {_verdict_word(link)}")
    return " · ".join(segments)


def _split_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    """Partition argv into (links, unknown flags).

    A link is never `--`-prefixed, and no flags remain — variants are inferred
    from the link's marker cages — so any `--` token is unknown and reported
    back for the caller to reject, never fed to the decoder."""
    links: list[str] = []
    unknown: list[str] = []
    for arg in argv:
        if arg.startswith("--"):
            unknown.append(arg)
        else:
            links.append(arg)
    return links, unknown


def main(argv: Sequence[str], stdin: TextIO, stderr: TextIO = sys.stderr) -> int:
    links, unknown = _split_args(argv)
    for flag in unknown:
        print(f"unknown flag: {flag}", file=stderr)
    links = links or [line.strip() for line in stdin if line.strip()]
    if not links:
        print("usage: inspect_link.py '<link>' ...", file=stderr)
        return 2
    for link in links:
        try:
            print(inspect_link(link))
        except Exception as exc:  # dev tool: a bad link must not kill the batch
            print(f"error: {exc}", file=stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], sys.stdin))
