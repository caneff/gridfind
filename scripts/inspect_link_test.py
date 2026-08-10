"""Behaviour of the SudokuMaker-link constraint classifier.

The classifier is display-only — it reports how gridfind's decode policy would
treat each constraint, so a rejected link explains itself. Precedence:
`disabled` wins over everything, then the known ruleset (type 0/1), then a live
payload marks it active, else inert.
"""

from __future__ import annotations

import pytest
from inspect_link import _display_size, _fmt_bucket, classify_constraint


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
