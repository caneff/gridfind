"""On-demand E2E suite: real SudokuMaker links driven through `cli.main`, the
CLI front door.

Each case file under `links/` holds the argv `cli.main` receives: any flag
lines, then the link, one per line. Links are URL-encoded and carry no
spaces, so the loader builds argv by `content.split()`. The filename stem
starts `found-`, `broke-`, or `invalid-`; the loader partitions on the first
`-` for the expected outcome.

A `found` case gets two layers of assertion: the front-door contract (exit
0, `found` on stdout, a grid follows), and an *independent* witness check —
`validate_witness` recovers the grid the CLI printed and checks it against
the `Puzzle` `decode_link` recovers from the same link, never calling
`verdict()` itself. A `broke` case trusts the curator's label: exit 1,
`broke` on stdout, nothing more. An `invalid` case is a
malformed link the front door refuses before any verdict: exit 2, the error
on stderr.

Deselected from the default run by `-m "not e2e"` in `pyproject.toml`'s
addopts; run on demand with `just e2e`.
"""

import io
import json
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
from lzstring import LZString

from gridfind import cli
from gridfind.sudokumaker import (
    DECODER_REGISTRY,
    decode_link,
    has_live_data,
)
from gridfind.witness_validator import validate_witness

LINKS_DIR = Path(__file__).parent / "links"


def _link_cases() -> list[Path]:
    cases = sorted(LINKS_DIR.rglob("*.txt"))
    if not cases:
        # A glob that finds nothing must fail here. Left unchecked, an empty
        # list parametrizes into zero cases and the corpus passes by
        # vanishing.
        msg = f"no link case files under {LINKS_DIR}"
        raise RuntimeError(msg)
    return cases


_CASES = _link_cases()


@pytest.mark.e2e
@pytest.mark.parametrize("path", _CASES, ids=[path.stem for path in _CASES])
def test_link_case_matches_its_filename_verdict(
    path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    expected_kind, _, _ = path.stem.partition("-")
    assert expected_kind in ("found", "broke", "invalid")
    argv = path.read_text().split()

    code = cli.main(argv, io.StringIO())

    captured = capsys.readouterr()

    # An `invalid-*` case is a malformed link the front door refuses before any
    # verdict: exit 2, the error on stderr, nothing on stdout.
    if expected_kind == "invalid":
        assert code == 2
        assert "invalid puzzle document" in captured.err
        return

    lines = captured.out.split("\n")
    assert lines[0] == expected_kind

    if expected_kind == "found":
        assert code == 0
        link = argv[-1]
        puzzle, _ = decode_link(link)
        assert validate_witness("\n".join(lines[1:]), puzzle)
    else:
        assert code == 1


# Wire types 0 (givens) and 1 (regions) are excluded from the one-to-one
# DECODER_REGISTRY loop below: 0 names no variant of its own, and 1 is shared
# by two variants (classic vs jigsaw, told apart by regions shape, not wire
# type) — both handled by the explicit list beside it instead (ADR-0007).
_NON_VARIANT_WIRE_TYPES = frozenset({0, 1})

# The link-reachable variants that don't map one-to-one onto a DECODER_REGISTRY
# wire type: classic and jigsaw both ride wire type 1 (told apart by their
# decoded regions shape), Schrödinger and doubler each arrive by a named
# marker cage that synthesizes their constraint, never a wire type of their
# own (ADR-0007/0008), equality arrives by a named cage-selector cage that
# graduates to `cage` + `equality-cage`, somedoku arrives by a named `type 1000`
# custom constraint or `type 2001` cosmetic cage — a global flag, not a registry
# wire type of its own (ADR-0017) — rellik arrives by a named `type 2001`
# cosmetic cage the same way killer does (ADR-0018), synthesizing its own
# `rellik-cage` constraint rather than a registry wire type of its own, and
# kropki-negative shares wire type 200 with plain white-kropki (told apart by
# whether a decoded `pair-difference` carries `negate`), so type 200's own
# found/broke pair doesn't also prove the negative rule.
_EXPLICIT_VARIANTS = (
    "classic",
    "jigsaw",
    "schrodinger",
    "doubler",
    "equality",
    "somedoku",
    "rellik",
    "kropki-negative",
)


def _wire_payload(link: str) -> dict[str, Any]:
    """The raw SudokuMaker puzzle JSON behind a link, mirroring
    `scripts/inspect_link.py`'s `decode_payload` — kept local for the same
    reason: the coverage gate classifies by raw wire *type*, which
    `decode_link`'s `Puzzle` no longer carries once XV/kropki are rewritten
    onto their own aliased constraint names."""
    payload = link.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(urllib.parse.unquote(payload))
    data: Any = json.loads(raw)["puzzle"]
    return data


def _active_wire_types(link: str) -> set[int]:
    """The `DECODER_REGISTRY` wire types this link carries a live rule for —
    an enabled, non-disabled constraint block whose payload `has_live_data`
    (the same predicate the decoder itself drops unmodeled constraints by)."""
    blocks = _wire_payload(link).get("constraints", [])
    if not isinstance(blocks, list):
        return set()
    return {
        block["type"]
        for block in blocks
        if isinstance(block, dict)
        and block.get("disabled") is not True
        and has_live_data(block)
    }


def _variant_tags(argv: list[str]) -> set[int | str]:
    """Every link-reachable variant one case file exercises: the explicit
    classic/jigsaw/schrodinger/doubler/somedoku/rellik/kropki-negative bucket,
    plus any DECODER_REGISTRY wire type whose payload carries a live rule.
    Schrödinger and doubler are inferred from the decoded puzzle's synthesized
    constraints (a marker cage stands them up); somedoku the same way (a
    global-flag component stands up `line-count-distinct` in place of the
    classic triplet, ADR-0017); rellik the same way again (a named
    `Rellik`/`Anti` cosmetic cage stands up `rellik-cage` alongside classic
    uniqueness, ADR-0018); classic vs jigsaw is told apart by whether the
    decoded regions-distinct constraint carries a custom `regions` matrix;
    kropki-negative is told apart from plain white-kropki by whether a decoded
    `pair-difference` constraint carries `negate`."""
    link = argv[-1]
    puzzle, _ = decode_link(link)
    constraint_types = {c.type for c in puzzle.constraints}
    schrodinger = "schrodinger" in constraint_types
    doubler = "doubler" in constraint_types
    equality = "equality-cage" in constraint_types
    somedoku = "line-count-distinct" in constraint_types
    rellik = "rellik-cage" in constraint_types
    kropki_negative = any(
        c.type == "pair-difference" and c.params.get("negate")
        for c in puzzle.constraints
    )
    tags: set[int | str] = set()
    if schrodinger:
        tags.add("schrodinger")
    if doubler:
        tags.add("doubler")
    if equality:
        tags.add("equality")
    if somedoku:
        tags.add("somedoku")
    if rellik:
        tags.add("rellik")
    if kropki_negative:
        tags.add("kropki-negative")
    # classic vs jigsaw is a plain link's own identity; a Schrödinger, doubler,
    # or somedoku case carries its own variant marker and doesn't double as
    # classic coverage — somedoku in particular decodes with no
    # regions-distinct constraint at all, so it would otherwise misclassify
    # as classic below. An equality, kropki-negative, or rellik link still
    # carries classic uniqueness, so it doubles as classic coverage and is not
    # excluded here.
    if not schrodinger and not doubler and not somedoku:
        jigsaw = any(
            c.type == "regions-distinct" and "regions" in c.params
            for c in puzzle.constraints
        )
        tags.add("jigsaw" if jigsaw else "classic")
    tags |= _active_wire_types(link)
    return tags


@pytest.mark.e2e
def test_coverage_floor_every_link_reachable_variant_has_found_and_broke() -> None:
    """The gate: every link-reachable variant — the
    one-to-one DECODER_REGISTRY wire types (driven off the registry itself,
    never hand-listed) plus the explicit classic/jigsaw/schrodinger cases —
    owes a `found-*` and a `broke-*` file under `links/`. Adding a new
    decoder without its two links must turn this red."""
    coverage: dict[int | str, dict[str, bool]] = {}
    for path in _CASES:
        kind, _, _ = path.stem.partition("-")
        # `invalid-*` cases carry a malformed link `decode_link` won't read, so
        # they name no variant and owe no found/broke pair.
        if kind not in ("found", "broke"):
            continue
        argv = path.read_text().split()
        for tag in _variant_tags(argv):
            slot = coverage.setdefault(tag, {"found": False, "broke": False})
            slot[kind] = True

    missing: list[str] = []
    for wire_type, decoded in DECODER_REGISTRY.items():
        if wire_type in _NON_VARIANT_WIRE_TYPES:
            continue
        slot = coverage.get(wire_type, {"found": False, "broke": False})
        missing += [
            f"{decoded.name} (wire type {wire_type}): missing {kind}-*"
            for kind in ("found", "broke")
            if not slot[kind]
        ]
    for variant in _EXPLICIT_VARIANTS:
        slot = coverage.get(variant, {"found": False, "broke": False})
        missing += [
            f"{variant}: missing {kind}-*"
            for kind in ("found", "broke")
            if not slot[kind]
        ]

    assert not missing, "coverage-floor gaps under links/: " + "; ".join(missing)
