"""The `gridfind` command, tested at its one seam: `main(argv, stdin) -> int`.

Each test hands `main` an argv and a stdin, captures stdout/stderr via capsys,
and asserts the printed verdict, the rendered witness, and the exit code — never
a private helper. The `found` and `broke` cases run the real `verdict` over the
same by-construction corpus documents `population_test.py` uses.
"""

import io
import json
import re
from pathlib import Path

import pytest
from lzstring import LZString

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
FOUND_6X6_DOC = (
    POPULATIONS_DIR
    / "board-rows-distinct-cols-distinct-regions-distinct"
    / "found-legal-6x6-sudoku-partial.json"
)
FOUND_4X4_DOC = (
    POPULATIONS_DIR
    / "board-rows-distinct-cols-distinct-regions-distinct"
    / "found-legal-4x4-sudoku-partial.json"
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
    # render deterministically: R1C1=1, R1C4=2 sit in row 1. Box borders are
    # box-drawing lines, with a solid divider between box row-groups
    # (issue #124).
    grid = lines[1:]
    assert grid[0] == "┌───────────┬───────────┬───────────┐"
    assert re.fullmatch(r"│ 1   \d   \d │ 2   \d   \d │ \d   \d   \d │", grid[1])
    assert grid[6] == "├───────────┼───────────┼───────────┤"


@pytest.mark.parametrize(
    ("doc", "size", "box_rows", "box_cols"),
    [(FOUND_6X6_DOC, 6, 2, 3), (FOUND_4X4_DOC, 4, 2, 2)],
    ids=["6x6", "4x4"],
)
def test_found_prints_rows_with_box_aware_spacing(
    capsys: pytest.CaptureFixture[str],
    doc: Path,
    size: int,
    box_rows: int,
    box_cols: int,
) -> None:
    code = cli.main([str(doc)], io.StringIO())

    out = capsys.readouterr().out
    lines = out.rstrip("\n").split("\n")
    assert code == 0
    assert lines[0] == "found"

    grid = lines[1:]
    # n+1 border rows interleave with n cell rows: a solid divider at every
    # box_rows-th border, a bordered row of box_cols-grouped cells otherwise
    # (BOX_SHAPE[size] = (box_rows, box_cols), issue #124).
    assert len(grid) == 2 * size + 1

    cell_rows = grid[1::2]
    assert len(cell_rows) == size
    for line in cell_rows:
        parts = line.split("│")
        assert parts[0] == ""
        assert parts[-1] == ""
        box_texts = parts[1:-1]
        assert len(box_texts) == size // box_cols
        for box_text in box_texts:
            digits = box_text.split()
            assert len(digits) == box_cols
            assert all(1 <= int(d) <= size for d in digits)

    border_rows = grid[0::2]
    assert len(border_rows) == size + 1
    for index, line in enumerate(border_rows):
        is_box_boundary = index in (0, size) or index % box_rows == 0
        assert ("─" in line) == is_box_boundary


def test_sudokumaker_link_argument_prints_found_and_grid(
    capsys: pytest.CaptureFixture[str], classic_link: str
) -> None:
    code = cli.main([classic_link], io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert code == 0
    assert lines[0] == "found"
    # R1C1=7 is a placement in the #54 link, so it renders deterministically.
    # lines[1] is the top border; lines[2] is the first cell row.
    assert re.fullmatch(r"│ 7   \d   \d │ \d   \d   \d │ \d   \d   \d │", lines[2])


def test_sudokumaker_link_on_stdin_matches_argument(
    capsys: pytest.CaptureFixture[str], classic_link: str
) -> None:
    code = cli.main([], io.StringIO(f"{classic_link}\n"))

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def _solvable_jigsaw_link() -> str:
    """A synthesised, fully-given `type 1` link whose regions are a broken
    diagonal partition, not the classic 3x3 boxes (issue #125). The grid
    val(r, c) = (r + c) % 9 + 1 is a Latin square where rows, columns, *and*
    every r - c ≡ k (mod 9) diagonal each hold all nine digits, so filling
    every cell as a given makes the puzzle trivially solvable against this
    jigsaw partition."""
    cells = []
    regions = []
    for i in range(81):
        row, col = divmod(i, 9)
        cells.append({"value": (row + col) % 9 + 1, "given": True})
        regions.append((row - col) % 9)
    puzzle = {
        "cells": cells,
        "constraints": [{"type": 0}, {"type": 1, "regions": regions}],
    }
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle}
    payload = LZString.compressToEncodedURIComponent(json.dumps(doc))
    return f"https://sudokumaker.app/?puzzle={payload}"


def test_solvable_jigsaw_link_prints_found_and_region_bordered_witness(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.main([_solvable_jigsaw_link()], io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert code == 0
    assert lines[0] == "found"
    # Every cell is given, so the digits render deterministically: row 0 is
    # 1..9 in order. The jigsaw borders don't line up with 3x3 boxes — no
    # vertical border sits at a multiple-of-3 column throughout the row.
    grid = lines[1:]
    cell_row = grid[1]
    assert [int(d) for d in re.findall(r"\d", cell_row)] == list(range(1, 10))
    assert grid[0] != "┌───────────┬───────────┬───────────┐"


def _classic_schrodinger_solution_link() -> str:
    """A synthesised, fully-given/pinned classic Schrödinger link (issue
    #143): a valid completed 1-9 Latin square (the well-known
    `(r*3 + r//3 + c) % 9 + 1` sudoku-by-formula construction, same shape as
    `_solvable_jigsaw_link`) with one cell per row/column/box promoted to an
    S-cell pinned red with center marks `{0, base}` — 0 is the domain's tenth
    digit and never appears among the ordinary givens, so every
    row/column/box ends up holding exactly the ten digits 0-9 once each. The
    S-cell positions are picked by `stack = (band + k) % 3` (band = row // 3,
    k = row % 3), a transversal that lands one S-cell in every row, column,
    and box. Fully constrained (every cell a given or an exact S-cell pin),
    so the default solve decides `found` instantly rather than searching."""
    s_cells = {}
    for band in range(3):
        for k in range(3):
            row = band * 3 + k
            stack = (band + k) % 3
            s_cells[(row, stack * 3 + band)] = True

    cells = []
    for row in range(9):
        for col in range(9):
            base = (row * 3 + row // 3 + col) % 9 + 1
            if (row, col) in s_cells:
                cells.append({"colors": 2, "candidates": 1 | (1 << base)})
            else:
                cells.append({"given": True, "value": base})

    puzzle = {"cells": cells, "minDigit": 0, "constraints": [{"type": 0}]}
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle}
    payload = LZString.compressToEncodedURIComponent(json.dumps(doc))
    return f"https://sudokumaker.app/?puzzle={payload}"


def test_schrodinger_link_with_flags_prints_found_and_s_cell_witness(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = _classic_schrodinger_solution_link()

    code = cli.main(["--schrodinger", "--reading", "classic", link], io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert code == 0
    assert lines[0] == "found"
    # R1C1 is the (0, 0) S-cell pinned to {0, 1} — renders deterministically.
    assert "{0 1}" in out


def test_schrodinger_flag_without_reading_defaults_to_classic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = _classic_schrodinger_solution_link()

    code = cli.main(["--schrodinger", link], io.StringIO())

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def test_unsupported_reading_exits_two_with_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = _classic_schrodinger_solution_link()

    code = cli.main(["--schrodinger", "--reading", "sum-valued", link], io.StringIO())

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("gridfind:")


def test_non_schrodinger_link_without_flag_is_unaffected(
    capsys: pytest.CaptureFixture[str], classic_link: str
) -> None:
    # No regression (#143): the classic link decodes exactly as before when
    # --schrodinger is not given.
    code = cli.main([classic_link], io.StringIO())

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def test_non_classic_link_exits_two_with_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.main(
        ["https://sudokumaker.app/?puzzle=not-a-real-payload"], io.StringIO()
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("gridfind:")


def test_file_path_containing_sudokumaker_app_is_still_read_as_a_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    # The sniff matches the #60 link shapes, not the bare host substring: a real
    # path that merely contains `sudokumaker.app/` must read as a document.
    doc = tmp_path / "sudokumaker.app" / "found.json"
    doc.parent.mkdir()
    doc.write_text(FOUND_DOC.read_text())

    code = cli.main([str(doc)], io.StringIO())

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


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


def test_malformed_puzzle_exits_two_with_stderr(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    # Valid JSON, but a given naming a digit the board never offers —
    # MalformedPuzzleError, not a json/schema-shape ValueError (issue #107).
    # The CLI must catch it too, not just report/verdict callers.
    doc = tmp_path / "malformed.json"
    doc.write_text(
        '{"puzzle": {"board": {"size": 4}, "constraints": [], '
        '"givens": [{"address": "R1C1", "digit": 9}]}, '
        '"working_state": {"places": [], "candidates": []}}'
    )

    code = cli.main([str(doc)], io.StringIO())

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
