"""The `gridfind` command, tested at its one seam: `main(argv, stdin) -> int`.

Each test hands `main` an argv and a stdin, captures stdout/stderr via capsys,
and asserts the printed verdict, the rendered witness, and the exit code — never
a private helper. The `found` and `broke` cases run the real `verdict` over
plain document literals, materialized to a file with `_write_doc` when a test
needs a real path.
"""

import io
import json
from pathlib import Path

import pytest
from lzstring import LZString

from gridfind import cli
from gridfind.verdict import Verdict

FOUND_DOC: dict[str, object] = {
    "puzzle": {
        "board": {"size": 9},
        "constraints": [
            {"type": "rows-distinct"},
            {"type": "cols-distinct"},
            {"type": "regions-distinct"},
        ],
        "givens": [
            {"address": "R1C1", "digit": 1},
            {"address": "R1C4", "digit": 2},
            {"address": "R4C1", "digit": 3},
            {"address": "R4C4", "digit": 4},
        ],
    },
    "working_state": {
        "places": [{"address": "R5C5", "digit": 5}],
        "candidates": [{"address": "R6C6", "digits": [5, 6, 7]}],
    },
}
BROKE_DOC: dict[str, object] = {
    "puzzle": {
        "board": {"size": 9},
        "constraints": [
            {"type": "rows-distinct"},
            {"type": "cols-distinct"},
            {"type": "regions-distinct"},
        ],
        "givens": [
            {"address": "R1C1", "digit": 5},
            {"address": "R2C2", "digit": 5},
        ],
    },
    "working_state": {"places": [], "candidates": []},
}


def _write_doc(tmp_path: Path, name: str, doc: dict[str, object]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(doc))
    return path


def test_found_prints_verdict_then_witness_grid(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    # The CLI wiring only: a found verdict prints the word, then the rendered
    # witness grid follows. The grid's shape and box borders are the renderer's
    # own contract, proven in witness_test.py — not re-derived here through the
    # slow solver front door.
    code = cli.main([str(_write_doc(tmp_path, "found.json", FOUND_DOC))], io.StringIO())

    out = capsys.readouterr().out
    lines = out.rstrip("\n").split("\n")
    assert code == 0
    assert lines[0] == "found"
    assert len(lines) > 1  # a grid body follows the verdict word


def test_sudokumaker_link_argument_prints_found_and_grid(
    capsys: pytest.CaptureFixture[str], classic_link: str
) -> None:
    # The argv link-sniff path: a bare SudokuMaker URL is decoded and solved.
    # The rendered grid is the renderer's contract (witness_test.py), so this
    # asserts only the CLI routing, not the grid shape.
    code = cli.main([classic_link], io.StringIO())

    out = capsys.readouterr().out
    lines = out.rstrip("\n").split("\n")
    assert code == 0
    assert lines[0] == "found"
    assert len(lines) > 1  # a grid body follows the verdict word


def test_sudokumaker_link_on_stdin_matches_argument(
    capsys: pytest.CaptureFixture[str], classic_link: str
) -> None:
    code = cli.main([], io.StringIO(f"{classic_link}\n"))

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def _classic_schrodinger_solution_link(
    first_s_cell_marks: set[int] | None = None,
) -> str:
    """A synthesised, fully-given/pinned classic Schrödinger link: a valid
    completed 1-9 Latin square (the well-known
    `(r*3 + r//3 + c) % 9 + 1` sudoku-by-formula construction, same shape as
    `_solvable_jigsaw_link`) with one cell per row/column/box promoted to an
    S-cell pinned via its own marker-cage `value` `"0,base"` (ADR-0014) — 0 is
    the domain's tenth digit and never appears among the ordinary givens, so
    every row/column/box ends up holding exactly the ten digits 0-9 once each.
    The S-cell positions are each their own single-cell cage entry in one
    `S-cell` marker block (no color flag), picked by `stack = (band + k) % 3`
    (band = row // 3, k = row % 3), a transversal that lands one S-cell in
    every row, column, and box. Fully constrained (every cell a given or an
    exact cage-pinned S-cell), so the default solve decides `found` instantly
    rather than searching.

    `first_s_cell_marks` optionally sets center marks on the first S-cell
    position (R1C1, pinned `{0, 1}`), the caged cell's own consistency
    restriction: marks containing the pinned pair keep the puzzle found, marks
    that miss it read broke."""
    s_cells = {}
    for band in range(3):
        for k in range(3):
            row = band * 3 + k
            stack = (band + k) % 3
            s_cells[(row, stack * 3 + band)] = True
    marked_position = next(iter(s_cells)) if first_s_cell_marks else None

    cells = []
    s_cell_cages = []
    for row in range(9):
        for col in range(9):
            base = (row * 3 + row // 3 + col) % 9 + 1
            if (row, col) in s_cells:
                index = row * 9 + col
                marks = first_s_cell_marks if (row, col) == marked_position else None
                cell = {"candidates": sum(1 << d for d in marks)} if marks else {}
                cells.append(cell)
                s_cell_cages.append({"value": f"0,{base}", "cells": [index]})
            else:
                cells.append({"given": True, "value": base})

    puzzle = {
        "cells": cells,
        "minDigit": 0,
        "constraints": [
            {"type": 0},
            {"name": "S-cell", "type": 2001, "cages": s_cell_cages},
        ],
    }
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle}
    payload = LZString.compressToEncodedURIComponent(json.dumps(doc))
    return f"https://sudokumaker.app/?puzzle={payload}"


def _classic_schrodinger_link_with_a_settled_scell_position() -> str:
    """The same transversal as `_classic_schrodinger_solution_link`, but over
    domain `1..10` (`minDigit: 1`, so the extra tenth digit is `10`, the
    domain's *maximum* — unlike that fixture's `0`, its minimum, `10` can sit
    in a settled cell's free upper slot without tripping the Schrödinger
    layer's `d0 < d1` canonicalization). The row-0/col-0/box-0 S-cell position
    is settled to a plain given of its own `base` digit instead of pinned via
    the marker cage. That position was the sole source of `10` in its row,
    column, and box: read as a **singleton pin** (ADR-0014, `is_s == 0`) it
    leaves `10` unplaceable in all three — broke: the pin holds `is_s == 0`, so
    the solver cannot make this cell the S-cell `{base, 10}` that alone could
    supply the missing `10`."""
    s_cells = {}
    for band in range(3):
        for k in range(3):
            row = band * 3 + k
            stack = (band + k) % 3
            s_cells[(row, stack * 3 + band)] = True
    settled_position = next(iter(s_cells))

    cells = []
    s_cell_cages = []
    for row in range(9):
        for col in range(9):
            base = (row * 3 + row // 3 + col) % 9 + 1
            if (row, col) in s_cells and (row, col) != settled_position:
                index = row * 9 + col
                cells.append({})
                s_cell_cages.append({"value": f"{base},10", "cells": [index]})
            else:
                cells.append({"given": True, "value": base})

    puzzle = {
        "cells": cells,
        "minDigit": 1,
        "constraints": [
            {"type": 0},
            {"name": "S-cell", "type": 2001, "cages": s_cell_cages},
        ],
    }
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle}
    payload = LZString.compressToEncodedURIComponent(json.dumps(doc))
    return f"https://sudokumaker.app/?puzzle={payload}"


def test_settled_digit_where_the_solution_needs_an_s_cell_is_broke(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Spec #348: a settled large digit is a singleton pin (is_s == 0), so a
    # cell whose only valid completion is an S-cell is not absorbed as its
    # lower half — the puzzle reads broke, not found.
    link = _classic_schrodinger_link_with_a_settled_scell_position()

    code = cli.main([link], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out.split("\n")[0] == "broke"


@pytest.mark.parametrize(
    ("marks", "expected_code", "expected_word"),
    [
        pytest.param({0, 1, 5}, 0, "found", id="stray-but-containing-mark-found"),
        pytest.param({3, 4}, 1, "broke", id="marks-contradict-the-pair-broke"),
    ],
)
def test_center_marks_layer_a_consistency_check_on_the_cage_pin(
    marks: set[int],
    expected_code: int,
    expected_word: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # R1C1's cage pins the pair {0, 1}; the cell's own center marks layer a
    # consistency restriction over that pin. Marks that contain the pair (with a
    # stray extra) stay found; marks that miss it read broke — the solver's
    # judgment, surfaced through the CLI front door.
    link = _classic_schrodinger_solution_link(first_s_cell_marks=marks)

    code = cli.main([link], io.StringIO())

    assert code == expected_code
    assert capsys.readouterr().out.split("\n")[0] == expected_word


@pytest.mark.parametrize(
    "flag",
    ["--schrodinger", "--doubler", "--reading", "--ignore-unknown-named-cages"],
    ids=["schrodinger", "doubler", "reading", "ignore-unknown-named-cages"],
)
def test_retired_variant_flags_are_rejected(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # The color channel is gone: the CLI no longer accepts the variant flags,
    # so argparse refuses them (exit 2) rather than silently ignoring them.
    # --ignore-unknown-named-cages retired alongside it (ADR-0012, #435): the
    # uniform warn-drop policy leaves no refusal for it to downgrade.
    link = _classic_schrodinger_solution_link()

    with pytest.raises(SystemExit) as exc:
        cli.main([flag, link], io.StringIO())

    assert exc.value.code == 2


def _classic_named_cage_link(name: str, cage_value: int) -> str:
    """A synthesised, fully-given classic 4x4 solution (a 2x2-box Latin grid,
    no doublers) carrying a single `type 2001` cosmetic cage over R1C1-R1C3
    named `name`. `cage_value` is the cage's stored sum — 9 matches the
    solution's own R1C1+R1C2+R1C3."""
    solution = [3, 2, 4, 1, 4, 1, 3, 2, 2, 3, 1, 4, 1, 4, 2, 3]
    regions = [(i // 4 // 2) * 2 + (i % 4 // 2) for i in range(16)]
    cells: list[dict[str, object]] = [{"given": True, "value": d} for d in solution]
    puzzle = {
        "cells": cells,
        "size": 4,
        "constraints": [
            {"type": 0},
            {"type": 1, "regions": regions},
            {
                "name": name,
                "type": 2001,
                "cages": [{"cells": [0, 1, 2], "value": str(cage_value)}],
            },
        ],
    }
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle}
    payload = LZString.compressToEncodedURIComponent(json.dumps(doc))
    return f"https://sudokumaker.app/?puzzle={payload}"


def test_unrecognized_named_cage_warns_and_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # An unrecognized name carries no rule (ADR-0012, #435): the cage is
    # dropped with a loud stderr warning, and the rest of the link — a
    # complete, valid solution grid with no other constraint — still verdicts
    # found.
    link = _classic_named_cage_link("Foobar", cage_value=9)

    code = cli.main([link], io.StringIO())

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.split("\n")[0] == "found"
    assert "Foobar" in captured.err


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
    # The sniff matches the link shapes, not the bare host substring: a real
    # path that merely contains `sudokumaker.app/` must read as a document.
    doc = tmp_path / "sudokumaker.app" / "found.json"
    doc.parent.mkdir()
    doc.write_text(json.dumps(FOUND_DOC))

    code = cli.main([str(doc)], io.StringIO())

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def test_broke_prints_word_alone(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code = cli.main([str(_write_doc(tmp_path, "broke.json", BROKE_DOC))], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out == "broke\n"


def test_reads_the_same_document_from_stdin(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.main([], io.StringIO(json.dumps(FOUND_DOC)))

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def test_unknown_prints_word_alone(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Classic 9x9 always decides fast, so `unknown` can't be produced through
    # the real solver at this seam; stub the verdict to force the branch.
    monkeypatch.setattr(cli, "verdict", lambda *a, **k: Verdict(kind="unknown"))
    code = cli.main([str(_write_doc(tmp_path, "found.json", FOUND_DOC))], io.StringIO())

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
    # MalformedPuzzleError, not a json/schema-shape ValueError.
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
