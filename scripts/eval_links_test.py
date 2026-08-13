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
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

from eval_links import (
    LinkView,
    _ApprovalHandler,
    _stems_from_git_paths,
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


def test_changed_stems_reads_diff_and_porcelain_including_renames() -> None:
    # `--changed` unions a bare `git diff --name-only` (edited-in-place fixtures)
    # with `git status --porcelain` (staged/unstaged/untracked). A porcelain
    # line carries a two-column status prefix, and a rename names both sides
    # after ` -> `; the parser reads paths off whitespace, so the prefix and the
    # arrow fall away and both the new and stale-old stems surface.
    diff_out = "src/gridfind/links/found-doubler-4x4.txt\n"
    status_out = (
        " M src/gridfind/links/broke-schrodinger-4x4.txt\n"
        "?? src/gridfind/links/found-combined-4x4.txt\n"
        "R  src/gridfind/links/old-name-4x4.txt -> "
        "src/gridfind/links/new-name-4x4.txt\n"
    )

    stems = _stems_from_git_paths(diff_out, status_out)

    assert stems == {
        "found-doubler-4x4",
        "broke-schrodinger-4x4",
        "found-combined-4x4",
        "old-name-4x4",
        "new-name-4x4",
    }


def test_changed_stems_ignores_non_txt_paths() -> None:
    # The corpus is `*.txt`; a changed script or doc alongside the fixtures is
    # not a link to eval, so it never becomes a stem.
    stems = _stems_from_git_paths(
        " M scripts/eval_links.py\n M src/gridfind/links/found-classic-4x4.txt\n"
    )

    assert stems == {"found-classic-4x4"}


_FOUND = LinkView(
    kind="found",
    puzzle_link="https://sudokumaker.app/?puzzle=PUZZLE",
    witness_grid="grid",
    solution_link="https://sudokumaker.app/?puzzle=SOLUTION",
)
_BROKE = LinkView(
    kind="broke",
    puzzle_link="https://sudokumaker.app/?puzzle=BROKE",
    witness_grid=None,
    solution_link=None,
)


def test_render_page_shows_one_active_slide_and_a_progress_counter() -> None:
    # The page is a slideshow: every link is its own slide, but only the first
    # is active on load, and a counter tracks position within the total.
    html = render_page([("a", _BROKE), ("b", _FOUND), ("c", _BROKE)])

    assert html.count('<section class="slide') == 3  # one slide per link
    assert html.count('class="slide active"') == 1  # exactly one is shown
    assert 'class="slide active" data-slide="0"' in html  # and it is the first
    assert '<span id="pos">1</span>' in html  # starting position
    assert '<span id="total">3</span>' in html  # of the total


def test_render_page_mounts_the_puzzle_lazily_not_eagerly() -> None:
    # A SudokuMaker iframe boots its whole app the moment it gets a src, even
    # when hidden — so the puzzle link rides in data-src and the JS assigns src
    # only when the slide becomes active. An eager src would boot every slide.
    html = render_page([("found-cage-4x4", _FOUND)])

    assert 'data-src="https://sudokumaker.app/?puzzle=PUZZLE"' in html
    # a leading space marks an eager `src=` — `data-src=` is preceded by `-`
    assert ' src="https://sudokumaker.app/?puzzle=PUZZLE"' not in html


def test_render_page_found_slide_carries_the_solution_iframe() -> None:
    html = render_page([("found-cage-4x4", _FOUND)])

    assert 'data-src="https://sudokumaker.app/?puzzle=SOLUTION"' in html


def test_render_page_broke_slide_shows_no_solution_pane() -> None:
    html = render_page([("broke-xv-4x4", _BROKE)])

    assert "no solution — broke case" in html  # the right pane says so
    # the puzzle is still there to judge, but there is no solution to mount
    assert 'data-src="https://sudokumaker.app/?puzzle=BROKE"' in html
    assert "puzzle=SOLUTION" not in html


def test_render_page_keeps_the_button_onclick_attribute_intact() -> None:
    # The stem argument sits inside a double-quoted onclick attribute, so its
    # own quotes must be HTML-escaped — a raw `"` closes the attribute early
    # and the handler never fires when clicked.
    html = render_page([("found-cage-4x4", _FOUND)])

    assert 'onclick="flag(this, &quot;found-cage-4x4&quot;)"' in html
    assert 'onclick="approve(this, &quot;found-cage-4x4&quot;)"' in html
    # the broken shape — a bare quote that terminates the attribute — is gone
    assert 'flag(this, "found-cage-4x4"' not in html


def test_render_page_note_field_is_addressable_by_the_flag_handler() -> None:
    # The flag() handler reads getElementById("note-" + stem); the slide must
    # give its textarea exactly that id, or the note reads null and the flag
    # throws. Pin the id to the stem the same slide hands the flag button.
    html = render_page([("found-cage-4x4", _FOUND)])

    assert 'id="note-found-cage-4x4"' in html
    assert "flag(this, &quot;found-cage-4x4&quot;)" in html


def _post(port: int, path: str, data: bytes) -> int:
    """POST to the running handler and return the status code, treating a 4xx
    as an answer rather than an exception."""
    try:
        return urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{port}{path}", method="POST", data=data
            ),
            timeout=5,
        ).status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_flag_endpoint_records_a_valid_flag_and_rejects_bad_ones(
    tmp_path: Path,
) -> None:
    # The server half of the Flag button: a known stem with a non-empty comment
    # is recorded and answered 200; an unknown stem or an empty comment is
    # refused 400 and nothing is written.
    flags = tmp_path / "flagged.json"
    _ApprovalHandler.page = render_page([])
    _ApprovalHandler.known = frozenset({"found-cage-4x4"})
    _ApprovalHandler.flags = flags
    server = HTTPServer(("127.0.0.1", 0), _ApprovalHandler)
    port = server.server_address[1]
    serve = threading.Thread(target=server.serve_forever)
    serve.start()
    try:
        good = _post(port, "/flag", b'{"stem": "found-cage-4x4", "comment": "off"}')
        unknown = _post(port, "/flag", b'{"stem": "ghost", "comment": "off"}')
        empty = _post(port, "/flag", b'{"stem": "found-cage-4x4", "comment": "  "}')
    finally:
        server.shutdown()
        server.server_close()
        serve.join(timeout=5)

    assert (good, unknown, empty) == (200, 400, 400)
    assert load_flags(flags) == [{"stem": "found-cage-4x4", "comment": "off"}]


def test_render_page_offers_an_end_state_with_a_close_control() -> None:
    # After the last slide an end-state screen appears with a Close control.
    # (The /finish behavior it drives is covered end-to-end by
    # test_finish_endpoint_stops_the_server.)
    html = render_page([("found-cage-4x4", _FOUND)])

    assert 'id="done"' in html  # the end-state screen
    assert ">Close</button>" in html  # its Close control


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
