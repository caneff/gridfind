"""Report which decodable features the eval-link corpus covers, found and broke.

A drift guard. Every decodable feature should have at least one `found-` link
and one `broke-` link in `src/gridfind/links/`; a whole feature covered on only
one side (or neither) is a coverage hole. This answers that at the wire-type and
cosmetic-cage-kind level only — it does not see sub-feature edges (an empty vs a
non-empty `negative` list, one diagonal vs both). Those need a human read.

    uv run python scripts/audit_link_coverage.py

Exits non-zero when any hole exists, so it can gate later.

The feature universe is read from `DECODER_REGISTRY` (every wire type gridfind
decodes) plus the cosmetic-cage marker kinds, so a newly decodable type appears
automatically. A modifier reaches the universe only through one of those two
channels: a registry row or a marker kind.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, get_args

# inspect_link owns the raw-payload decode and the disabled/known/active/inert
# classification; reuse both instead of a second decode of the same link.
from inspect_link import classify_constraint, decode_payload

from gridfind.sudokumaker.dropped import constraint_name
from gridfind.sudokumaker.naming import Role, classify, named_component
from gridfind.sudokumaker.registry import DECODER_REGISTRY
from gridfind.sudokumaker.wire_types import COSMETIC_CAGE_TYPE, CUSTOM_CONSTRAINT_TYPE

_LINKS_DIR = Path(__file__).resolve().parents[1] / "src" / "gridfind" / "links"

# The two verdict sides a corpus link declares through its filename prefix. A
# feature covered on only one side (or neither) is a hole.
_SIDES = ("found", "broke")


def feature_universe() -> list[str]:
    """Every feature a corpus link could exercise: one row per decodable wire
    type (its registry name), plus one `cage:<kind>` row per cosmetic-cage
    marker kind."""
    names = [decoded.name for decoded in DECODER_REGISTRY.values()]
    kinds = [f"cage:{kind}" for kind in get_args(Role)]
    return names + kinds


def link_features(payload: Mapping[str, object]) -> set[str]:
    """The features one decoded puzzle exercises: the registry name of each
    non-disabled constraint, plus `cage:<kind>` for each non-disabled cosmetic
    cage. A disabled constraint is switched off, so it exercises nothing.
    A `global-flag` name (naming.py — `Somedoku`, `Numbered Rooms`) rides a
    `type 1000` custom constraint's `definition.name` as well as a `type 2001`
    cosmetic cage's top-level `name`, so that second carrier is checked here
    too, keyed on the `named_component` shape rather than a hand-rolled
    per-name read."""
    features: set[str] = set()
    constraints: Any = payload.get("constraints") or []
    for constraint in constraints:
        if classify_constraint(constraint) == "disabled":
            continue
        decoded = DECODER_REGISTRY.get(constraint.get("type"))
        if decoded is not None:
            features.add(decoded.name)
        if constraint.get("type") == COSMETIC_CAGE_TYPE:
            features.add(f"cage:{classify(constraint.get('name'))}")
        elif constraint.get("type") == CUSTOM_CONSTRAINT_TYPE:
            component = named_component(constraint_name(constraint))
            if component is not None and component.shape == "global-flag":
                features.add(f"cage:{component.role}")
    return features


def build_coverage(links_dir: Path) -> dict[str, dict[str, int]]:
    """Tally, per feature, how many `found-` and how many `broke-` links
    exercise it. Only these two verdict sides count — a `malformed-` link is a
    decode-error case, not verdict coverage. Any other prefix is an unexpected
    corpus filename: warn to stderr (the repo's fail-loud norm) rather than let
    it slip out of the tally unseen."""
    coverage: dict[str, dict[str, int]] = {
        feature: dict.fromkeys(_SIDES, 0) for feature in feature_universe()
    }
    for link_file in sorted(links_dir.glob("*.txt")):
        side = link_file.name.split("-", 1)[0]
        if side == "malformed":
            continue
        if side not in _SIDES:
            print(
                f"skipping unexpected corpus filename: {link_file.name}",
                file=sys.stderr,
            )
            continue
        for feature in link_features(decode_payload(link_file.read_text().strip())):
            coverage.setdefault(feature, dict.fromkeys(_SIDES, 0))[side] += 1
    return coverage


def find_holes(coverage: dict[str, dict[str, int]]) -> list[str]:
    """One message per feature missing a `found` or a `broke` link (or both)."""
    holes: list[str] = []
    for feature, counts in coverage.items():
        missing = [side for side in _SIDES if counts[side] == 0]
        if missing:
            holes.append(f"{feature}: no {' and no '.join(missing)} link")
    return holes


def format_report(coverage: dict[str, dict[str, int]], holes: list[str]) -> str:
    """The matrix, then the holes list (or a clean-bill line)."""
    width = max(len(feature) for feature in coverage)
    rows = [
        f"  {feature:<{width}}  found={counts['found']:<2}  broke={counts['broke']}"
        for feature, counts in coverage.items()
    ]
    body = ["Eval-link coverage (wire-type / cage-kind level):", *rows, ""]
    if holes:
        body.append(f"{len(holes)} hole(s):")
        body += [f"  - {hole}" for hole in holes]
    else:
        body.append("No holes: every feature has a found and a broke link.")
    return "\n".join(body)


def main(links_dir: Path = _LINKS_DIR) -> int:
    coverage = build_coverage(links_dir)
    holes = find_holes(coverage)
    print(format_report(coverage, holes))
    return 1 if holes else 0


if __name__ == "__main__":
    raise SystemExit(main())
