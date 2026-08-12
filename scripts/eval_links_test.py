"""The human-eval view's pure seam: one case file's argv reduced to what a
person needs to verify the verdict by eye — the puzzle link, and (when found)
the witness grid and a filled-in solution link.

Covered end to end on two tiny synthetic links, one already-solved (found)
and one already-contradictory (broke), mirroring `verify_links_test.py` —
the glue with `decode_link`/`verdict`/`verify_link` is checked without
touching the real `links/` corpus.
"""

from __future__ import annotations

from pathlib import Path

from eval_links import (
    LinkView,
    eval_link,
    load_approved,
    load_flags,
    pending_stems,
    record_approval,
    record_flag,
    render_page,
)

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


def test_load_approved_on_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_approved(tmp_path / "nope.json") == set()


def test_record_approval_round_trips(tmp_path: Path) -> None:
    store = tmp_path / "approved.json"

    record_approval(store, "found-cage-4x4")

    assert load_approved(store) == {"found-cage-4x4"}


def test_record_approval_is_idempotent(tmp_path: Path) -> None:
    store = tmp_path / "approved.json"

    record_approval(store, "found-cage-4x4")
    record_approval(store, "found-cage-4x4")
    record_approval(store, "broke-xv-4x4")

    assert load_approved(store) == {"found-cage-4x4", "broke-xv-4x4"}


def test_load_flags_on_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_flags(tmp_path / "nope.json") == []


def test_record_flag_round_trips(tmp_path: Path) -> None:
    store = tmp_path / "flagged.json"

    record_flag(store, "found-cage-4x4", "witness looks off")

    assert load_flags(store) == [
        {"stem": "found-cage-4x4", "comment": "witness looks off"}
    ]


def test_record_flag_accumulates_several_flags_on_one_stem(tmp_path: Path) -> None:
    store = tmp_path / "flagged.json"

    record_flag(store, "found-cage-4x4", "first note")
    record_flag(store, "found-cage-4x4", "second note")

    # A second flag adds an entry, never replaces the first.
    assert load_flags(store) == [
        {"stem": "found-cage-4x4", "comment": "first note"},
        {"stem": "found-cage-4x4", "comment": "second note"},
    ]


def test_pending_stems_hides_approved_by_default() -> None:
    stems = ["a", "b", "c"]

    pending = pending_stems(stems, approved={"b"}, show_all=False)

    assert pending == ["a", "c"]  # order preserved, b dropped


def test_pending_stems_show_all_keeps_everything() -> None:
    stems = ["a", "b", "c"]

    pending = pending_stems(stems, approved={"b"}, show_all=True)

    assert pending == ["a", "b", "c"]


def test_render_page_shows_both_links_and_an_approve_control_for_a_found_card() -> None:
    view = LinkView(
        kind="found",
        puzzle_link="https://sudokumaker.app/?puzzle=PUZZLE",
        witness_grid="grid",
        solution_link="https://sudokumaker.app/?puzzle=SOLUTION",
    )

    html = render_page([("found-cage-4x4", view)])

    assert 'href="https://sudokumaker.app/?puzzle=PUZZLE"' in html
    assert 'href="https://sudokumaker.app/?puzzle=SOLUTION"' in html
    assert "found-cage-4x4" in html
    assert "<button" in html


def test_render_page_shows_a_comment_field_flag_control_and_count_badge() -> None:
    view = LinkView(
        kind="found",
        puzzle_link="https://sudokumaker.app/?puzzle=PUZZLE",
        witness_grid="grid",
        solution_link="https://sudokumaker.app/?puzzle=SOLUTION",
    )

    html = render_page([("found-cage-4x4", view)], counts={"found-cage-4x4": 2})

    assert "<textarea" in html  # a place to jot the note
    assert "flag(" in html  # the Flag control carries the stem
    assert "found-cage-4x4" in html
    assert "2 flagged" in html  # the current flag count badge


def test_render_page_omits_the_solution_link_for_a_broke_card() -> None:
    view = LinkView(
        kind="broke",
        puzzle_link="https://sudokumaker.app/?puzzle=PUZZLE",
        witness_grid=None,
        solution_link=None,
    )

    html = render_page([("broke-xv-4x4", view)])

    assert 'href="https://sudokumaker.app/?puzzle=PUZZLE"' in html
    assert "broke-xv-4x4" in html
    assert "<button" in html  # still approvable
    assert "solution" not in html.lower()
