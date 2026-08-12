"""The human-eval view's pure seam: one case file's argv reduced to what a
person needs to verify the verdict by eye — the puzzle link, and (when found)
the witness grid and a filled-in solution link.

Covered end to end on two tiny synthetic links, one already-solved (found)
and one already-contradictory (broke), mirroring `verify_links_test.py` —
the glue with `decode_link`/`verdict`/`verify_link` is checked without
touching the real `links/` corpus.
"""

from __future__ import annotations

import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

from eval_links import (
    LinkView,
    _ApprovalHandler,
    archive_flags,
    eval_link,
    load_approved,
    load_archive,
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


def test_archive_flags_moves_covered_stems_stamped_and_leaves_the_rest(
    tmp_path: Path,
) -> None:
    flagged = tmp_path / "flagged.json"
    archive = tmp_path / "archive.json"
    record_flag(flagged, "found-cage-4x4", "witness off")
    record_flag(flagged, "broke-xv-4x4", "leave me")

    archive_flags(flagged, archive, {"found-cage-4x4"}, issue_number=312)

    # The covered stem left the store, stamped with the map it fed...
    assert load_archive(archive) == [
        {"stem": "found-cage-4x4", "comment": "witness off", "issue": 312}
    ]
    # ...and the uncovered stem stayed put, untouched.
    assert load_flags(flagged) == [{"stem": "broke-xv-4x4", "comment": "leave me"}]


def test_archive_flags_accumulates_across_calls(tmp_path: Path) -> None:
    flagged = tmp_path / "flagged.json"
    archive = tmp_path / "archive.json"
    record_flag(flagged, "a", "first batch")
    record_flag(flagged, "b", "second batch")

    archive_flags(flagged, archive, {"a"}, issue_number=1)
    archive_flags(flagged, archive, {"b"}, issue_number=2)

    # The earlier archived batch survives the later one.
    assert load_archive(archive) == [
        {"stem": "a", "comment": "first batch", "issue": 1},
        {"stem": "b", "comment": "second batch", "issue": 2},
    ]
    assert load_flags(flagged) == []


def test_archive_flags_with_no_stems_moves_nothing(tmp_path: Path) -> None:
    flagged = tmp_path / "flagged.json"
    archive = tmp_path / "archive.json"
    record_flag(flagged, "a", "stay")

    archive_flags(flagged, archive, set(), issue_number=9)

    assert load_archive(archive) == []
    assert load_flags(flagged) == [{"stem": "a", "comment": "stay"}]


def test_pending_stems_hides_approved_by_default() -> None:
    stems = ["a", "b", "c"]

    pending = pending_stems(stems, approved={"b"}, show_all=False)

    assert pending == ["a", "c"]  # order preserved, b dropped


def test_pending_stems_show_all_keeps_everything() -> None:
    stems = ["a", "b", "c"]

    pending = pending_stems(stems, approved={"b"}, show_all=True)

    assert pending == ["a", "b", "c"]


def test_flagging_a_stem_leaves_it_pending_next_run(tmp_path: Path) -> None:
    # A flag hides a link only for the live session; unlike an approval it must
    # come back next run. Pending is filtered by the approved log alone, so a
    # flagged-but-unapproved stem stays pending — flagging must never approve.
    flag_log = tmp_path / "flagged.json"
    record_flag(flag_log, "b", "looks off")

    approved = load_approved(tmp_path / "approved.json")  # nothing approved
    pending = pending_stems(["a", "b", "c"], approved, show_all=False)

    assert pending == ["a", "b", "c"]  # the flagged "b" is still there


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


def test_render_page_keeps_the_button_onclick_attribute_intact() -> None:
    # The stem argument sits inside a double-quoted onclick attribute, so its
    # own quotes must be HTML-escaped — a raw `"` closes the attribute early
    # and the handler never fires when clicked.
    view = LinkView(
        kind="found",
        puzzle_link="https://sudokumaker.app/?puzzle=PUZZLE",
        witness_grid="grid",
        solution_link="https://sudokumaker.app/?puzzle=SOLUTION",
    )

    html = render_page([("found-cage-4x4", view)])

    assert 'onclick="flag(this, &quot;found-cage-4x4&quot;)"' in html
    assert 'onclick="approve(this, &quot;found-cage-4x4&quot;)"' in html
    # the broken shape — a bare quote that terminates the attribute — is gone
    assert 'flag(this, "found-cage-4x4"' not in html


def _flag_js(page: str) -> str:
    """The body of the page's `flag()` handler, sliced out so assertions bind
    to it rather than to the identically-shaped `approve()`."""
    start = page.index("async function flag(")
    return page[start : page.index("</script>", start)]


def test_render_page_flag_removes_its_card_on_a_successful_flag() -> None:
    # A flag hides the card for this session (it returns next run), so on
    # success flag() removes the card and refreshes the count — the same visible
    # acknowledgement approve() gives — with a disable while the POST is in
    # flight so the click plainly registers.
    view = LinkView(
        kind="found",
        puzzle_link="https://sudokumaker.app/?puzzle=PUZZLE",
        witness_grid="grid",
        solution_link="https://sudokumaker.app/?puzzle=SOLUTION",
    )

    flag_js = _flag_js(render_page([("found-cage-4x4", view)]))

    assert "btn.disabled = true" in flag_js  # disabled while the flag is sent
    assert 'document.getElementById("card-" + stem).remove()' in flag_js
    assert "flagged ✓" not in flag_js  # no bump-and-keep; the card leaves


def test_render_page_offers_a_finish_control() -> None:
    # A person can end the run from the page itself, not only with Ctrl+C.
    view = LinkView(
        kind="broke",
        puzzle_link="https://sudokumaker.app/?puzzle=PUZZLE",
        witness_grid=None,
        solution_link=None,
    )

    html = render_page([("broke-xv-4x4", view)])

    assert "finish()" in html  # a control that calls the finish handler
    assert "async function finish(" in html  # the handler that ends the run
    assert "/finish" in html  # it posts to the finish endpoint


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


def test_finish_endpoint_stops_the_server() -> None:
    # POST /finish must end the run: the handler answers 200, then shuts the
    # server down from a side thread so serve_forever() returns on its own.
    _ApprovalHandler.page = render_page([])
    _ApprovalHandler.known = frozenset()
    server = HTTPServer(("127.0.0.1", 0), _ApprovalHandler)
    port = server.server_address[1]
    serve = threading.Thread(target=server.serve_forever)
    serve.start()
    try:
        resp = urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/finish", method="POST", data=b""
            ),
            timeout=5,
        )
        status = resp.status
        serve.join(timeout=5)  # serve_forever returns once shutdown lands
    finally:
        server.shutdown()
        server.server_close()
        serve.join(timeout=5)

    assert status == 200
    assert not serve.is_alive()  # the server really stopped
