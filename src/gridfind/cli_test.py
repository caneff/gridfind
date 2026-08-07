"""The `gridfind` command, tested at its one seam: `main(argv, stdin) -> int`.

Each test hands `main` an argv and a stdin, captures stdout/stderr via capsys,
and asserts the printed verdict, the rendered witness, and the exit code — never
a private helper. The `found` and `broke` cases run the real `verdict` over the
same by-construction corpus documents `population_test.py` uses.
"""

import io
import re
from pathlib import Path

import pytest

from gridfind import cli
from gridfind.verdict import Verdict

POPULATIONS_DIR = Path(__file__).parent / "populations"
FOUND_DOC = (
    POPULATIONS_DIR
    / "board-rows-distinct-cols-distinct-regions-distinct"
    / "found-legal-classic-sudoku-partial.json"
)
BROKE_DOC = (
    POPULATIONS_DIR
    / "board-rows-distinct-cols-distinct-regions-distinct"
    / "broke-duplicate-digit-in-box.json"
)


def test_found_prints_verdict_then_witness_grid(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.main([str(FOUND_DOC)], io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert code == 0
    assert lines[0] == "found"

    # The witness is solver-chosen, but the givens are pinned, so their cells
    # render deterministically: R1C1=1, R1C4=2 sit in row 1. Box gaps are a
    # double space; box row-groups are separated by a blank line.
    grid = lines[1:]
    assert re.fullmatch(r"1 \d \d  2 \d \d  \d \d \d", grid[0])
    assert grid[3] == ""  # blank row after the first box-row


def test_broke_prints_word_alone(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main([str(BROKE_DOC)], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out == "broke\n"


def test_reads_the_same_document_from_stdin(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.main([], io.StringIO(FOUND_DOC.read_text()))

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def test_unknown_prints_word_alone(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Classic 9x9 always decides fast, so `unknown` can't be produced through
    # the real solver at this seam; stub the verdict to force the branch.
    monkeypatch.setattr(cli, "verdict", lambda *a, **k: Verdict(kind="unknown"))
    code = cli.main([str(FOUND_DOC)], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out == "unknown\n"


def test_help_shows_example_command_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--help"], io.StringIO())

    out = capsys.readouterr().out
    assert "gridfind puzzle.json" in out
    assert "gridfind < puzzle.json" in out


def test_empty_input_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main([], io.StringIO(""))

    captured = capsys.readouterr()
    assert code == 2
    assert "usage:" in captured.err.lower()


def test_malformed_json_exits_nonzero_with_stderr(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")

    code = cli.main([str(bad)], io.StringIO())

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("gridfind:")


def test_missing_file_exits_nonzero_with_stderr(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code = cli.main([str(tmp_path / "nope.json")], io.StringIO())

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("gridfind:")
