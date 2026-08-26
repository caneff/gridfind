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

from gridfind.sudokumaker import link_to_document

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
        pytest.param({"size": 9}, 100, 9, id="size"),
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
    assert code == 2


def test_main_prints_the_report_line_for_a_valid_link(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Drives the happy path through `main` itself, not just `inspect_link` —
    # a break in `main`'s own print/loop wiring must fail here even when
    # `inspect_link` still works.
    stem = "found-xv-9x9"
    path = next(p for p in _LINK_CASES if p.stem == stem)
    link = path.read_text().split()[-1]

    code = main([link], io.StringIO())

    assert code == 0
    assert capsys.readouterr().out == _GOLDEN_REPORTS[stem] + "\n"


def test_main_reports_a_bad_link_error_on_stderr_and_still_exits_zero() -> None:
    # A rejected link is a per-link failure, not a batch failure: `main`
    # catches it, reports it on stderr, and still exits 0 (a bad link among
    # good ones must not kill the batch).
    path = next(p for p in _LINK_CASES if p.stem.startswith("malformed"))
    link = path.read_text().split()[-1]
    err = io.StringIO()

    code = main([link], io.StringIO(), stderr=err)

    assert code == 0
    assert "error: " in err.getvalue()


def test_decode_payload_matches_link_to_document() -> None:
    """`decode_payload` and `link_to_document` read the same boundary — the
    corpus's `puzzle` block must agree byte-for-byte, whichever one decoded
    it."""
    for path in _LINK_CASES:
        link = path.read_text().split()[-1]
        assert decode_payload(link) == link_to_document(link)["puzzle"], path.stem


# Golden report lines for every corpus link that `link_to_puzzle` accepts,
# pinned so a decode-boundary refactor can't silently change what the
# inspector reports (malformed-* links error out of `inspect_link` itself and
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
    "broke-black-kropki-negative-4x4": (
        "4x4 · 16 cells · 4 givens · types {0,1,201} · active: 201 · verdict: broke"
    ),
    "broke-between-4x4": (
        "4x4 · 16 cells · 3 givens · types {0,1,403} · active: 403 · verdict: broke"
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
    "broke-cosmetic-cage-unnamed-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-cosmetic-cage-unrecognized-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-doubler-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,2001} · active: 2001x2 · verdict: broke"
    ),
    "broke-equality-middle-9x9": (
        "9x9 · 81 cells · 5 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-equality-parity-9x9": (
        "9x9 · 81 cells · 5 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-equality-rank-9x9": (
        "9x9 · 81 cells · 5 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-even-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,100} · active: 100 · verdict: broke"
    ),
    "broke-extra-region-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,305} · active: 305 · verdict: broke"
    ),
    "broke-grouped-entropic-9x9": (
        "9x9 · 81 cells · 3 givens · types {0,1,406} · active: 406 · verdict: broke"
    ),
    "broke-grouped-parity-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,406} · active: 406 · verdict: broke"
    ),
    "broke-indexing-col-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,601} · active: 601 · verdict: broke"
    ),
    "broke-indexing-row-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,600} · active: 600 · verdict: broke"
    ),
    "broke-indexing-scell-col-4x4": (
        "4x4 · 16 cells · 3 givens · types {0,1,601,2001} ·"
        " active: 601, 2001 · verdict: broke"
    ),
    "broke-jigsaw-6x6": "6x6 · 36 cells · 2 givens · types {0,1} · verdict: broke",
    "broke-kropki-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: broke"
    ),
    "broke-kropki-negative-4x4": (
        "4x4 · 16 cells · 4 givens · types {0,1,200} · active: 200 · verdict: broke"
    ),
    "broke-kropki-negative-doubler-6x6": (
        "6x6 · 36 cells · 4 givens · types {0,1,200,2001} ·"
        " active: 200, 2001 · verdict: broke"
    ),
    "broke-kropki-non-default-value-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: broke"
    ),
    "broke-lockout-4x4": (
        "4x4 · 16 cells · 3 givens · types {0,1,407} · active: 407 · verdict: broke"
    ),
    "broke-negative-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10} · active: 10 · verdict: broke"
    ),
    "broke-numbered-rooms-6x6": (
        "8x8 · 64 cells · 9 givens · types {0,1,201,301,1000,2000} · active: "
        "301x2, 1000(Numbered Rooms), 201 · inert: 1000(JSON Postproc), 2000x3 "
        "· verdict: broke"
    ),
    "broke-odd-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,101} · active: 101 · verdict: broke"
    ),
    "broke-odd-doubler-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,101,2001} ·"
        " active: 101, 2001 · verdict: broke"
    ),
    "broke-positive-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,11} · active: 11 · verdict: broke"
    ),
    "broke-clone-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,302} · active: 302 · verdict: broke"
    ),
    "broke-clone-scell-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,302,2001} · active: 2001, 302 ·"
        " verdict: broke"
    ),
    "broke-palindrome-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,402} · active: 402 · verdict: broke"
    ),
    "broke-quadruple-4x4": (
        "4x4 · 16 cells · 4 givens · types {0,1,303} · active: 303 · verdict: broke"
    ),
    "broke-rellik-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,2001} · active: 2001 · verdict: broke"
    ),
    "broke-renban-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,400} · active: 400 · verdict: broke"
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
    "broke-somedoku-9x9": (
        "9x9 · 81 cells · 2 givens · types {1000} ·"
        " inert: 1000(Somedoku) · verdict: broke"
    ),
    "broke-thermo-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,300} · active: 300 · verdict: broke"
    ),
    "broke-thermo-doubler-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,300,2001} ·"
        " active: 300, 2001 · verdict: broke"
    ),
    "broke-whisper-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,401} · active: 401 · verdict: broke"
    ),
    "broke-x-sudoku-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10,11} ·"
        " active: 10, 11 · verdict: broke"
    ),
    "broke-xv-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,202} · active: 202 · verdict: broke"
    ),
    "broke-xv-negative-4x4": (
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
    "found-black-kropki-negative-4x4": (
        "4x4 · 16 cells · 4 givens · types {0,1,201} · active: 201 · verdict: found"
    ),
    "found-between-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,403} · active: 403 · verdict: found"
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
    "found-cosmetic-cage-unnamed-4x4": (
        "4x4 · 16 cells · 16 givens · types {0,1,2001} · active: 2001 · verdict: found"
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
    "found-equality-9x9": (
        "9x9 · 81 cells · 2 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-even-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,100} · active: 100 · verdict: found"
    ),
    "found-extra-region-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,305} · active: 305 · verdict: found"
    ),
    "found-grouped-entropic-9x9": (
        "9x9 · 81 cells · 3 givens · types {0,1,406} · active: 406 · verdict: found"
    ),
    "found-grouped-parity-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,406} · active: 406 · verdict: found"
    ),
    "found-indexing-col-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,601} · active: 601 · verdict: found"
    ),
    "found-indexing-row-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,600} · active: 600 · verdict: found"
    ),
    "found-indexing-scell-col-4x4": (
        "4x4 · 16 cells · 3 givens · types {0,1,601,2001} ·"
        " active: 601, 2001 · verdict: found"
    ),
    "found-jigsaw-6x6": "6x6 · 36 cells · 1 given · types {0,1} · verdict: found",
    "found-kropki-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: found"
    ),
    "found-kropki-negative-4x4": (
        "4x4 · 16 cells · 4 givens · types {0,1,200} · active: 200 · verdict: found"
    ),
    "found-kropki-negative-doubler-6x6": (
        "6x6 · 36 cells · 4 givens · types {0,1,200,2001} ·"
        " active: 200, 2001 · verdict: found"
    ),
    "found-kropki-non-default-value-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,200} · active: 200 · verdict: found"
    ),
    "found-lockout-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,407} · active: 407 · verdict: found"
    ),
    "found-negative-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10} · active: 10 · verdict: found"
    ),
    "found-numbered-rooms-6x6": (
        "8x8 · 64 cells · 9 givens · types {0,1,201,301,1000,2000} · active: "
        "301x2, 1000(Numbered Rooms), 201 · inert: 1000(JSON Postproc), 2000x3 "
        "· verdict: found"
    ),
    "found-odd-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,101} · active: 101 · verdict: found"
    ),
    "found-palindrome-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,402} · active: 402 · verdict: found"
    ),
    "found-positive-diagonal-only-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,11} · active: 11 · verdict: found"
    ),
    "found-clone-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,302} · active: 302 · verdict: found"
    ),
    "found-quadruple-4x4": (
        "4x4 · 16 cells · 1 given · types {0,1,303} · active: 303 · verdict: found"
    ),
    "found-rellik-4x4": (
        "4x4 · 16 cells · 0 givens · types {0,1,2001} · active: 2001 · verdict: found"
    ),
    "found-renban-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,400} · active: 400 · verdict: found"
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
    "found-somedoku-9x9": (
        "9x9 · 81 cells · 0 givens · types {1000} ·"
        " inert: 1000(Somedoku) · verdict: found"
    ),
    "found-thermo-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,300} · active: 300x2 · verdict: found"
    ),
    "found-thermo-doubler-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,300,2001} ·"
        " active: 300, 2001 · verdict: found"
    ),
    "found-whisper-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,401} · active: 401 · verdict: found"
    ),
    "found-x-sudoku-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,10,11} ·"
        " active: 10, 11 · verdict: found"
    ),
    "found-xv-9x9": (
        "9x9 · 81 cells · 0 givens · types {0,1,200,202,301} ·"
        " active: 301, 202, 200 · verdict: found"
    ),
    "found-xv-negative-4x4": (
        "4x4 · 16 cells · 2 givens · types {0,1,202} · active: 202 · verdict: found"
    ),
}

_GOLDEN_CASES = [path for path in _LINK_CASES if path.stem in _GOLDEN_REPORTS]


def test_golden_reports_cover_every_non_malformed_corpus_link() -> None:
    """A link case added under `links/` without a matching golden entry must
    fail here, not silently skip the pin."""
    non_malformed = {
        path.stem for path in _LINK_CASES if not path.stem.startswith("malformed")
    }
    assert set(_GOLDEN_REPORTS) == non_malformed


@pytest.mark.parametrize(
    "path", _GOLDEN_CASES, ids=[path.stem for path in _GOLDEN_CASES]
)
def test_inspect_link_report_is_pinned(path: Path) -> None:
    link = path.read_text().split()[-1]
    assert inspect_link(link) == _GOLDEN_REPORTS[path.stem]


def test_inspect_link_malformed_case_still_errors_the_same_way() -> None:
    """The one corpus link `link_to_puzzle` rejects must keep failing inside
    `inspect_link` itself (caught and reported by `main`, not the classifier)
    so the boundary refactor doesn't change which stage sees the error."""
    malformed = [path for path in _LINK_CASES if path.stem.startswith("malformed")]
    assert malformed, "expected a malformed-* corpus link"
    for path in malformed:
        link = path.read_text().split()[-1]
        with pytest.raises(Exception, match="not among"):
            inspect_link(link)
