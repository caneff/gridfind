"""Unit tests for the shared corpus-synthesis harness (`blank_cells`,
`place_givens`, `wrap_document`, `boxed_document`, `regenerate`) every
`synthesize_*_links.py` script builds on. The drift-guard proof that every
committed corpus file still matches its synthesizer lives in
`corpus_drift_test.py`, not here — this file tests the harness's own pieces
in isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import _corpus
import pytest


def test_blank_cells_is_size_squared_empty_dicts() -> None:
    cells = _corpus.blank_cells(3)
    assert cells == [{}] * 9


def test_blank_cells_returns_independent_dicts() -> None:
    cells = _corpus.blank_cells(2)
    cells[0]["given"] = True
    assert cells[1] == {}


def test_place_givens_sets_the_row_major_index() -> None:
    cells = _corpus.blank_cells(2)
    _corpus.place_givens(cells, 2, {(1, 2): 4})
    assert cells == [{}, {"given": True, "value": 4}, {}, {}]


def test_wrap_document_shapes_cells_size_and_constraints() -> None:
    cells = _corpus.blank_cells(2)
    constraints: list[dict[str, object]] = [{"type": 0}]
    document = _corpus.wrap_document(cells, 2, constraints)
    assert document == {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": 2, "constraints": constraints},
    }


def test_boxed_document_builds_blank_cells_places_givens_and_box_regions() -> None:
    document = _corpus.boxed_document(2, 2, givens={(1, 1): 3})
    puzzle = cast("dict[str, object]", document["puzzle"])
    constraints = cast("list[dict[str, object]]", puzzle["constraints"])
    assert puzzle["size"] == 4
    assert cast("list[object]", puzzle["cells"])[0] == {"given": True, "value": 3}
    assert constraints[0] == {"type": 0}
    assert constraints[1]["type"] == 1
    assert len(cast("list[object]", constraints[1]["regions"])) == 16


def test_boxed_document_appends_extra_constraints_after_the_box_pair() -> None:
    marker: dict[str, object] = {"type": 999}
    document = _corpus.boxed_document(2, 2, constraints=[marker])
    puzzle = cast("dict[str, object]", document["puzzle"])
    constraints = cast("list[dict[str, object]]", puzzle["constraints"])
    assert constraints[2] is marker


def test_boxed_document_honors_a_caller_built_cells_list() -> None:
    cells: list[dict[str, object]] = [{"candidates": 1} for _ in range(16)]
    document = _corpus.boxed_document(2, 2, cells=cells)
    puzzle = cast("dict[str, object]", document["puzzle"])
    assert puzzle["cells"] is cells


def test_regenerate_writes_each_corpus_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_corpus, "LINKS_DIR", tmp_path)
    _corpus.regenerate({"sample": lambda: "a link"})
    assert (tmp_path / "sample.txt").read_text() == "a link\n"


def test_synthesizer_by_stem_merges_every_modules_corpus() -> None:
    merged = _corpus.synthesizer_by_stem()
    modules = list(_corpus.discover_modules())
    assert len(merged) == sum(len(module.CORPUS) for module in modules)
    for module in modules:
        for name, fn in module.CORPUS.items():
            assert merged[name] is fn
