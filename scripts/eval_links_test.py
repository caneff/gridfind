"""The human-eval view's pure seam: one case file's argv reduced to what a
person needs to verify the verdict by eye — the puzzle link, and (when found)
the witness grid and a filled-in solution link.

Covered end to end on two tiny synthetic links, one already-solved (found)
and one already-contradictory (broke), mirroring `verify_links_test.py` —
the glue with `decode_link`/`verdict`/`verify_link` is checked without
touching the real `links/` corpus.
"""

from __future__ import annotations

from eval_links import eval_link

from gridfind.sudokumaker import encode_link

_WIRE_CONSTRAINTS = [{"type": 0}]


def _encode(puzzle_data: dict[str, object]) -> str:
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle_data}
    return encode_link(doc)


def test_eval_link_shows_witness_and_solution_for_a_found_case() -> None:
    # A fully-given, already-valid 2x2 Latin square: rows {1,2}/{2,1}.
    cells = [
        {"given": True, "value": 1},
        {"given": True, "value": 2},
        {"given": True, "value": 2},
        {"given": True, "value": 1},
    ]
    link = _encode({"cells": cells, "size": 2, "constraints": _WIRE_CONSTRAINTS})

    view = eval_link([link])

    assert view.kind == "found"
    assert view.puzzle_link == link
    assert view.witness_grid is not None
    # The solved digits appear in the rendered grid — it is a real witness.
    assert "1" in view.witness_grid
    assert "2" in view.witness_grid
    assert view.solution_link is not None
    assert view.solution_link.startswith("https://sudokumaker.app/?puzzle=")


def test_eval_link_shows_only_the_puzzle_for_a_broke_case() -> None:
    # Two givens in the same row share a digit — broke before any search.
    cells = [
        {"given": True, "value": 1},
        {"given": True, "value": 1},
        {},
        {},
    ]
    link = _encode({"cells": cells, "size": 2, "constraints": _WIRE_CONSTRAINTS})

    view = eval_link([link])

    assert view.kind == "broke"
    assert view.puzzle_link == link
    assert view.witness_grid is None
    assert view.solution_link is None
