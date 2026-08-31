"""Behaviour of the link/JSON round trip.

The contract is losslessness: a link decoded to JSON and encoded back is the
same link, and `encode` refuses to write one that isn't. Everything else here
is argument handling around that.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import link_file
import pytest
from link_file import encode, main, read_link

from gridfind.sudokumaker import document_to_link, link_to_document

_LINKS_DIR = Path(__file__).parent.parent / "src" / "gridfind" / "links"
_LINK_CASES = sorted(
    path for path in _LINKS_DIR.rglob("*.txt") if not path.stem.startswith("malformed")
)


def _link_of(path: Path) -> str:
    return path.read_text().split()[-1]


@pytest.mark.parametrize("path", _LINK_CASES, ids=lambda p: p.stem)
def test_decode_then_encode_preserves_the_document(path: Path, tmp_path: Path) -> None:
    """The whole point of the tool: a puzzle survives the trip through JSON.

    Compares documents, not link text. A link the app wrote and a link written
    here can compress to different payloads and still be the same puzzle, so
    string equality would fail on links that are perfectly intact.
    """
    link = _link_of(path)
    board, out = tmp_path / "board.json", tmp_path / "link.txt"

    assert main(["decode", link, str(board)], io.StringIO()) == 0
    assert main(["encode", str(board), str(out)], io.StringIO()) == 0

    assert link_to_document(out.read_text().strip()) == link_to_document(link)


@pytest.mark.parametrize("path", _LINK_CASES[:5], ids=lambda p: p.stem)
def test_decoded_json_is_the_whole_document_not_just_the_puzzle(path: Path) -> None:
    """`encode` can only restore fields `decode` kept, so the document must
    carry its `formatVersion` wrapper, not just the `puzzle` block."""
    document = link_to_document(_link_of(path))

    assert set(document) >= {"formatVersion", "puzzle"}


def test_an_edit_to_the_json_reaches_the_encoded_link(tmp_path: Path) -> None:
    """The tool exists to let you change a puzzle, not only to move it."""
    # Decoded JSON is an untyped external boundary — a local `Any` is deliberate
    # (CODING_STANDARDS: reach for Any only at genuine boundaries).
    document: Any = link_to_document(_link_of(_LINK_CASES[0]))
    document["puzzle"]["name"] = "renamed by the test"
    board = tmp_path / "board.json"
    board.write_text(json.dumps(document))
    out = tmp_path / "link.txt"

    assert main(["encode", str(board), str(out)], io.StringIO()) == 0

    reloaded: Any = link_to_document(out.read_text().strip())
    assert reloaded["puzzle"]["name"] == "renamed by the test"


def test_encode_writes_to_stdout_when_the_destination_is_a_dash(
    tmp_path: Path,
) -> None:
    document = link_to_document(_link_of(_LINK_CASES[0]))
    board = tmp_path / "board.json"
    board.write_text(json.dumps(document))
    stdout = io.StringIO()

    assert main(["encode", str(board), "-"], stdout) == 0

    assert stdout.getvalue().strip() == document_to_link(document)


def test_encode_refuses_a_document_that_does_not_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silently lossy link opens as a different puzzle; the guard must fire
    before anything is written.

    The guard watches the compression boundary, which no document reachable
    from JSON currently breaks — so the failure is injected at that boundary
    rather than faked with odd puzzle data.
    """
    board, out = tmp_path / "board.json", tmp_path / "link.txt"
    board.write_text(json.dumps({"formatVersion": "1.5.0", "puzzle": {"width": 9}}))
    monkeypatch.setattr(
        link_file, "document_to_link", lambda _: document_to_link({"puzzle": {}})
    )

    with pytest.raises(ValueError, match="round-trip"):
        encode(str(board), str(out), io.StringIO())

    assert not out.exists()


def test_read_link_accepts_a_file_or_the_link_itself(tmp_path: Path) -> None:
    """Links in sudokumaker-custom-constraints live in files; links pasted into
    a terminal do not."""
    link = _link_of(_LINK_CASES[0])
    holder = tmp_path / "PUZZLE_LINK.txt"
    holder.write_text(link + "\n")

    assert read_link(str(holder)) == link
    assert read_link(link) == link


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param([], id="no-args"),
        pytest.param(["decode"], id="missing-paths"),
        pytest.param(["frobnicate", "a", "b"], id="unknown-command"),
    ],
)
def test_main_rejects_bad_usage(argv: list[str]) -> None:
    stderr = io.StringIO()

    assert main(argv, io.StringIO(), stderr) == 2
    assert "usage:" in stderr.getvalue()


def test_main_reports_a_missing_source_without_raising(tmp_path: Path) -> None:
    stderr = io.StringIO()

    code = main(["encode", str(tmp_path / "nope.json"), "-"], io.StringIO(), stderr)

    assert code == 1
    assert "error: " in stderr.getvalue()
