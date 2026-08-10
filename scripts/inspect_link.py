"""Decode SudokuMaker link(s) and report structure + verdict, in one process.

A dev tool. `gridfind <link>` already answers "does it run"; this answers the
*other* question — "what's in it, and why did it reject" — by decoding the
link, classifying each constraint the way gridfind's decode policy treats it,
and running the verdict. Many links share one OR-Tools import, so a batch costs
one startup, not one per link.

    uv run python scripts/inspect_link.py '<link>' ['<link>' ...]
    printf '%s\n' "$l1" "$l2" | uv run python scripts/inspect_link.py
    uv run python scripts/inspect_link.py --schrodinger '<link>'
"""

from __future__ import annotations

import json
import math
import sys
import urllib.parse
from collections import Counter
from collections.abc import Sequence
from typing import Any, TextIO

from lzstring import LZString

from gridfind.engine import GridfindError
from gridfind.sudokumaker import constraint_name, decode_link, has_live_data
from gridfind.verdict import verdict

_KNOWN_TYPES = (0, 1)


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


def _decode_payload(link: str) -> dict[str, object]:
    """The SudokuMaker puzzle JSON behind a `?puzzle=` link (or bare payload).

    Mirrors `decode_link`'s boundary decode, kept local because `decode_link`
    consumes the raw dict and returns a `Puzzle` — the inspector needs the dict
    itself to classify constraints, including on links `decode_link` rejects.
    """
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    data: Any = json.loads(raw)["puzzle"]
    return data


def _display_size(data: dict[str, object], cell_count: int) -> int:
    """Board edge for the report line, most specific first (`width`, then
    `size`, else `isqrt(cells)`). Display only — the verdict path sizes the
    board authoritatively via `decode_link`."""
    for key in ("width", "size"):
        value = data.get(key)
        if isinstance(value, int):
            return value
    return math.isqrt(cell_count)


def _verdict_word(link: str, *, schrodinger: bool) -> str:
    """The verdict word for a link, or `rejected (<reason>)` when the decoder
    refuses it — so one bad link reports itself instead of killing the batch."""
    try:
        puzzle, state = decode_link(link, schrodinger=schrodinger)
    except (ValueError, GridfindError) as exc:
        return f"rejected ({exc})"
    return verdict(puzzle, state).kind


def _fmt_bucket(tags: list[str]) -> str:
    """`["2000", "2000", "201"]` -> `2000x2, 201` — collapse repeats to counts."""
    return ", ".join(
        f"{tag}x{count}" if count > 1 else tag for tag, count in Counter(tags).items()
    )


def inspect_link(link: str, *, schrodinger: bool) -> str:
    """One report line: size, givens, the constraint types present, each
    classification bucket that isn't empty, and the verdict."""
    # JSON values are untyped past the decode boundary — poke at them as Any.
    data: Any = _decode_payload(link)
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

    segments = [
        f"{size}x{size}",
        f"{len(cells)} cells",
        f"{givens} given{'' if givens == 1 else 's'}",
        "types {" + ",".join(str(t) for t in types) + "}",
    ]
    segments += [
        f"{label}: {_fmt_bucket(tags)}" for label, tags in buckets.items() if tags
    ]
    segments.append(f"verdict: {_verdict_word(link, schrodinger=schrodinger)}")
    return " · ".join(segments)


def main(argv: Sequence[str], stdin: TextIO) -> int:
    args = [a for a in argv if a != "--schrodinger"]
    schrodinger = "--schrodinger" in argv
    links = args or [line.strip() for line in stdin if line.strip()]
    if not links:
        print("usage: inspect_link.py [--schrodinger] '<link>' ...", file=sys.stderr)
        return 2
    for link in links:
        try:
            print(inspect_link(link, schrodinger=schrodinger))
        except Exception as exc:  # dev tool: a bad link must not kill the batch
            print(f"error: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], sys.stdin))
