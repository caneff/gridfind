"""Behaviour of the SudokuMaker-link constraint classifier.

The classifier is display-only — it reports how gridfind's decode policy would
treat each constraint, so a rejected link explains itself. Precedence:
`disabled` wins over everything, then the known ruleset (type 0/1), then a live
payload marks it active, else inert.
"""

from __future__ import annotations

import io

import pytest
from inspect_link import (
    _display_size,
    _fmt_bucket,
    _split_args,
    classify_constraint,
    main,
)


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


def test_main_survives_a_bare_flag_token() -> None:
    # A `--`-prefixed token with no link behind it leaves nothing to decode, so
    # it reaches the usage exit rather than the decoder (which raises on a
    # non-link).
    code = main(["--doubler"], io.StringIO(), stderr=io.StringIO())
    assert code == 2
