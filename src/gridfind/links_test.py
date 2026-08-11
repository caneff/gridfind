"""On-demand E2E suite: real SudokuMaker links driven through `cli.main`, the
CLI front door.

Each case file under `links/` holds the argv `cli.main` receives: any flag
lines, then the link, one per line. Links are URL-encoded and carry no
spaces, so the loader builds argv by `content.split()`. The filename stem
starts `found-` or `broke-`; the loader partitions on the first `-` for the
expected verdict.

A `found` case gets two layers of assertion: the front-door contract (exit
0, `found` on stdout, a grid follows), and an *independent* witness check —
`validate_witness` recovers the grid the CLI printed and checks it against
the `Puzzle` `decode_link` recovers from the same link, never calling
`verdict()` itself. A `broke` case trusts the curator's label: exit 1,
`broke` on stdout, nothing more (map #168 decision 2).

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
from gridfind.sudokumaker import DECODER_REGISTRY, decode_link, has_live_data
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
    assert expected_kind in ("found", "broke")
    argv = path.read_text().split()

    code = cli.main(argv, io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert lines[0] == expected_kind

    if expected_kind == "found":
        assert code == 0
        link = argv[-1]
        puzzle, _ = decode_link(
            link,
            schrodinger="--schrodinger" in argv,
            doubler="--doubler" in argv,
        )
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
# decoded regions shape), and Schrödinger and doubler each arrive by their own
# flag (`--schrodinger`, `--doubler`), never a wire type (ADR-0007/0008).
_EXPLICIT_VARIANTS = ("classic", "jigsaw", "schrodinger", "doubler")


def _wire_payload(link: str) -> dict[str, Any]:
    """The raw SudokuMaker puzzle JSON behind a link, mirroring
    `scripts/inspect_link.py`'s `_decode_payload` — kept local for the same
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
    classic/jigsaw/schrodinger bucket, plus any DECODER_REGISTRY wire type
    whose payload carries a live rule. Schrödinger is declared by the
    `--schrodinger` flag, never inferred; classic vs jigsaw is told apart by
    whether the decoded regions-distinct constraint carries a custom
    `regions` matrix."""
    link = argv[-1]
    schrodinger = "--schrodinger" in argv
    doubler = "--doubler" in argv
    tags: set[int | str] = set()
    if schrodinger:
        tags.add("schrodinger")
    if doubler:
        tags.add("doubler")
    # classic vs jigsaw is a flag-free link's own identity; a Schrödinger or
    # doubler case declares its variant by flag and doesn't double as classic
    # coverage.
    if not schrodinger and not doubler:
        puzzle, _ = decode_link(link, schrodinger=False)
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
