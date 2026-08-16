"""Behaviour of the SudokuMaker-link constraint classifier.

The classifier is display-only — it reports how gridfind's decode policy would
treat each constraint, so a rejected link explains itself. Precedence:
`disabled` wins over everything, then the known ruleset (type 0/1), then a live
payload marks it active, else inert.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from inspect_link import (
    _display_size,
    _fmt_bucket,
    _split_args,
    classify_constraint,
    decode_payload,
    inspect_link,
    main,
)

from gridfind.sudokumaker import decode_document

_LINKS_DIR = Path(__file__).parent.parent / "src" / "gridfind" / "links"
_LINK_CASES = sorted(_LINKS_DIR.rglob("*.txt"))


@pytest.mark.parametrize(
    ("constraint", "expected"),
    [
        pytest.param({"type": 0}, "known", id="givens-type-0"),
        pytest.param(
            {"type": 1, "regions": [0, 0, 1, 1]}, "known", id="regions-type-1"
        ),
        pytest.param(
            {"type": 405, "disabled": True, "lines": [[1, 2, 3]]},
            "disabled",
            id="disabled-wins-over-data",
        ),
        pytest.param(
            {"type": 201, "clues": [], "negative": []},
            "inert",
            id="empty-clues-inert",
        ),
        pytest.param(
            {"type": 1000, "input": {"groups": [{"cells": [25, 26, 20]}]}},
            "active",
            id="populated-groups-active",
        ),
        pytest.param(
            {"type": 301, "cages": [{"cells": [0, 1], "value": 0}]},
            "active",
            id="populated-cage-active",
        ),
        pytest.param(
            {"type": 2001, "cages": [{"value": "11", "cells": [0, 1, 2]}]},
            "active",
            id="graduated-cosmetic-cage-active",
        ),
        pytest.param(
            {"type": 2001, "cages": [{"value": "Total", "cells": [0, 1]}]},
            "active",
            id="non-numeric-cosmetic-cage-active",
        ),
        pytest.param(
            {"type": 2001, "cages": [{"value": "", "cells": [0, 1]}]},
            "active",
            id="empty-cosmetic-cage-active",
        ),
        # A global toggle carries its rule in the bare type, not a payload;
        # gridfind now honours all four, so the inspector calls them active.
        pytest.param({"type": 12}, "active", id="anti-king-toggle-active"),
        pytest.param({"type": 13}, "active", id="anti-knight-toggle-active"),
        pytest.param(
            {"type": 10, "style": {"color": "#34bbe6ff"}},
            "active",
            id="negative-diagonal-toggle-active",
        ),
        pytest.param(
            {"type": 11, "style": {"color": "#34bbe6ff"}},
            "active",
            id="positive-diagonal-toggle-active",
        ),
        # A disabled toggle never counts, whatever gridfind does with it enabled.
        pytest.param({"type": 12, "disabled": True}, "disabled", id="disabled-toggle"),
    ],
)
def test_classify_constraint(constraint: dict[str, object], expected: str) -> None:
    assert classify_constraint(constraint) == expected


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        pytest.param(["405"], "405", id="single"),
        pytest.param(["2000", "2000", "201"], "2000x2, 201", id="collapse-repeat"),
        pytest.param([], "", id="empty"),
    ],
)
def test_fmt_bucket(tags: list[str], expected: str) -> None:
    assert _fmt_bucket(tags) == expected


@pytest.mark.parametrize(
    ("data", "cell_count", "expected"),
    [
        pytest.param({"width": 6}, 36, 6, id="width-wins"),
        pytest.param({"width": 6, "size": 9}, 54, 6, id="width-over-size"),
        pytest.param({"size": 9}, 81, 9, id="size"),
        pytest.param({}, 16, 4, id="isqrt-fallback"),
    ],
)
def test_display_size(data: dict[str, object], cell_count: int, expected: int) -> None:
    assert _display_size(data, cell_count) == expected


@pytest.mark.parametrize(
    ("argv", "links", "unknown"),
    [
        pytest.param(
            ["u1", "u2"],
            ["u1", "u2"],
            [],
            id="links-only",
        ),
        pytest.param(
            ["u", "--bogus"],
            ["u"],
            ["--bogus"],
            id="unknown-flag-not-a-link",
        ),
        pytest.param(
            ["--doubler", "u"],
            ["u"],
            ["--doubler"],
            id="retired-flag-is-unknown-now",
        ),
        pytest.param([], [], [], id="empty"),
    ],
)
def test_split_args(argv: list[str], links: list[str], unknown: list[str]) -> None:
    assert _split_args(argv) == (links, unknown)


def test_main_reports_unknown_flag_without_decoding_it() -> None:
    err = io.StringIO()
    code = main(["--bogus"], io.StringIO(), stderr=err)
    assert "unknown flag: --bogus" in err.getvalue()
    assert code == 2  # nothing left to decode -> usage exit, not a crash


def test_decode_payload_matches_decode_document() -> None:
    """`decode_payload` and `decode_document` read the same boundary — the
    corpus's `puzzle` block must agree byte-for-byte, whichever one decoded
    it."""
    for path in _LINK_CASES:
        link = path.read_text().split()[-1]
        assert decode_payload(link) == decode_document(link)["puzzle"], path.stem


# Golden report lines for every corpus link that `decode_link` accepts,
# pinned so a decode-boundary refactor can't silently change what the
# inspector reports (invalid-* links error out of `inspect_link` itself and
# are exercised separately, through `main`, below).
_GOLDEN_REPORTS = {
    "broke-anti-king-6x6": (
        "6x6 · 36 cells · 2 givens · types {0,1,12} · active: 12 · verdict: broke"
    ),
    "broke-anti-knight-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,13} · active: 13 · verdict: broke"
    ),
    "broke-black-kropki-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,201} · active: 201 · verdict: broke"
    ),
    "broke-cage-4x4": (
        "4x4 · 16 cells · 3 givens · types {0,1,301} · active: 301 · verdict: broke"
    ),
    "broke-cage-sum-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,301} · active: 301 · verdict: broke"
    ),
    "broke-classic-4x4": "4x4 · 16 cells · 4 givens · types {0,1} · verdict: broke",
    "broke-constant-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,2001} · active: 2001x2 · verdict: broke"
    ),
    "broke-cosmetic-cage-sumless-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-doubler-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,2001} · active: 2001x2 · verdict: broke"
    ),
    "broke-jigsaw-6x6": "6x6 · 36 cells · 2 givens · types {0,1} · verdict: broke",
    "broke-kropki-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: broke"
    ),
    "broke-kropki-non-default-value-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: broke"
    ),
    "broke-negative-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10} · active: 10 · verdict: broke"
    ),
    "broke-positive-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,11} · active: 11 · verdict: broke"
    ),
    "broke-scell-caged-value-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-scell-consistency-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-schrodinger-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-thermo-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,300} · active: 300 · verdict: broke"
    ),
    "broke-x-sudoku-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10,11} ·"
        " active: 10, 11 · verdict: broke"
    ),
    "broke-xv-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,202} · active: 202 · verdict: broke"
    ),
    "found-anti-king-6x6": (
        "6x6 · 36 cells · 1 given · types {0,1,12} · active: 12 · verdict: found"
    ),
    "found-anti-knight-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,13} · active: 13 · verdict: found"
    ),
    "found-black-kropki-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,201} · active: 201 · verdict: found"
    ),
    "found-cage-4x4": (
        "4x4 · 16 cells · 4 givens · types {0,1,301} · active: 301 · verdict: found"
    ),
    "found-classic-4x4": "4x4 · 16 cells · 4 givens · types {0,1} · verdict: found",
    "found-classic-6x6": "6x6 · 36 cells · 6 givens · types {0,1} · verdict: found",
    "found-classic-9x9": "9x9 · 81 cells · 3 givens · types {0,1} · verdict: found",
    "found-cosmetic-cage-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-cosmetic-cage-unrecognized-4x4": (
        "4x4 · 16 cells · 16 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-doubled-scell-17cage-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001x2 ·"
        " inert: 2001 · verdict: found"
    ),
    "found-constant-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,2001} · active: 2001x2 · verdict: found"
    ),
    "found-doubler-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,2001} · active: 2001x2 · verdict: found"
    ),
    "found-jigsaw-6x6": "6x6 · 36 cells · 1 given · types {0,1} · verdict: found",
    "found-kropki-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: found"
    ),
    "found-kropki-non-default-value-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: found"
    ),
    "found-negative-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10} · active: 10 · verdict: found"
    ),
    "found-positive-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,11} · active: 11 · verdict: found"
    ),
    "found-scell-bare-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-scell-half-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-scell-pin-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-scell-stray-marks-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-schrodinger-6x6": (
        "6x6 · 36 cells · 2 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-somedoku-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,2001} · inert: 2001 · verdict: found"
    ),
    "found-thermo-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,300} · active: 300x2 · verdict: found"
    ),
    "found-x-sudoku-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10,11} ·"
        " active: 10, 11 · verdict: found"
    ),
    "found-xv-9x9": (
        "9x9 · 81 cells · 0 givens · types {0,1,200,202,301} ·"
        " active: 301, 202, 200 · verdict: found"
    ),
}

_GOLDEN_CASES = [path for path in _LINK_CASES if path.stem in _GOLDEN_REPORTS]


def test_golden_reports_cover_every_non_invalid_corpus_link() -> None:
    """A link case added under `links/` without a matching golden entry must
    fail here, not silently skip the pin."""
    non_invalid = {
        path.stem for path in _LINK_CASES if not path.stem.startswith("invalid")
    }
    assert set(_GOLDEN_REPORTS) == non_invalid


@pytest.mark.parametrize(
    "path", _GOLDEN_CASES, ids=[path.stem for path in _GOLDEN_CASES]
)
def test_inspect_link_report_is_pinned(path: Path) -> None:
    link = path.read_text().split()[-1]
    assert inspect_link(link) == _GOLDEN_REPORTS[path.stem]


def test_inspect_link_invalid_case_still_errors_the_same_way() -> None:
    """The one corpus link `decode_link` rejects must keep failing inside
    `inspect_link` itself (caught and reported by `main`, not the classifier)
    so the boundary refactor doesn't change which stage sees the error."""
    invalid = [path for path in _LINK_CASES if path.stem.startswith("invalid")]
    assert invalid, "expected an invalid-* corpus link"
    for path in invalid:
        link = path.read_text().split()[-1]
        with pytest.raises(Exception, match="not among"):
            inspect_link(link)
