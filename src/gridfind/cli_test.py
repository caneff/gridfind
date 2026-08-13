"""The `gridfind` command, tested at its one seam: `main(argv, stdin) -> int`.

Each test hands `main` an argv and a stdin, captures stdout/stderr via capsys,
and asserts the printed verdict, the rendered witness, and the exit code — never
a private helper. The `found` and `broke` cases run the real `verdict` over
plain document literals, materialized to a file with `_write_doc` when a test
needs a real path.
"""

import io
import json
import re
from pathlib import Path

import pytest
from lzstring import LZString

from gridfind import cli
from gridfind.conftest import FOUND_4X4_DOC
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
FOUND_6X6_DOC: dict[str, object] = {
    "puzzle": {
        "board": {"size": 6},
        "constraints": [
            {"type": "rows-distinct"},
            {"type": "cols-distinct"},
            {"type": "regions-distinct"},
        ],
        "givens": [
            {"address": "R1C1", "digit": 1},
            {"address": "R4C4", "digit": 2},
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
    code = cli.main([str(_write_doc(tmp_path, "found.json", FOUND_DOC))], io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert code == 0
    assert lines[0] == "found"

    # The witness is solver-chosen, but the givens are pinned, so their cells
    # render deterministically: R1C1=1, R1C4=2 sit in row 1. Box borders are
    # box-drawing lines, with a solid divider between box row-groups.
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
    tmp_path: Path,
    doc: dict[str, object],
    size: int,
    box_rows: int,
    box_cols: int,
) -> None:
    code = cli.main([str(_write_doc(tmp_path, "doc.json", doc))], io.StringIO())

    out = capsys.readouterr().out
    lines = out.rstrip("\n").split("\n")
    assert code == 0
    assert lines[0] == "found"

    grid = lines[1:]
    # n+1 border rows interleave with n cell rows: a solid divider at every
    # box_rows-th border, a bordered row of box_cols-grouped cells otherwise
    # (BOX_SHAPE[size] = (box_rows, box_cols)).
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
    # R1C1=7 is a placement in the classic link, so it renders deterministically.
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
    diagonal partition, not the classic 3x3 boxes. The grid
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
    """A synthesised, fully-given/pinned classic Schrödinger link: a valid
    completed 1-9 Latin square (the well-known
    `(r*3 + r//3 + c) % 9 + 1` sudoku-by-formula construction, same shape as
    `_solvable_jigsaw_link`) with one cell per row/column/box promoted to an
    S-cell pinned via its own marker-cage `value` `"0,base"` (spec #349) — 0 is
    the domain's tenth digit and never appears among the ordinary givens, so
    every row/column/box ends up holding exactly the ten digits 0-9 once each.
    The S-cell positions are each their own single-cell cage entry in one
    `S-cell` marker block (no color flag), picked by `stack = (band + k) % 3`
    (band = row // 3, k = row % 3), a transversal that lands one S-cell in
    every row, column, and box. Fully constrained (every cell a given or an
    exact cage-pinned S-cell), so the default solve decides `found` instantly
    rather than searching."""
    s_cells = {}
    for band in range(3):
        for k in range(3):
            row = band * 3 + k
            stack = (band + k) % 3
            s_cells[(row, stack * 3 + band)] = True

    cells = []
    s_cell_cages = []
    for row in range(9):
        for col in range(9):
            base = (row * 3 + row // 3 + col) % 9 + 1
            if (row, col) in s_cells:
                index = row * 9 + col
                cells.append({})
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


def test_schrodinger_marker_link_prints_found_and_s_cell_witness(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The link's S-cell marker cage declares the variant, so the CLI needs no
    # flag — Schrödinger-ness is inferred from the link.
    link = _classic_schrodinger_solution_link()

    code = cli.main([link], io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert code == 0
    assert lines[0] == "found"
    # R1C1 is the (0, 0) S-cell pinned to {0, 1} — renders deterministically.
    assert "{0 1}" in out


@pytest.mark.parametrize(
    "flag",
    ["--schrodinger", "--doubler", "--reading"],
    ids=["schrodinger", "doubler", "reading"],
)
def test_retired_variant_flags_are_rejected(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # The color channel is gone: the CLI no longer accepts the variant flags,
    # so argparse refuses them (exit 2) rather than silently ignoring them.
    link = _classic_schrodinger_solution_link()

    with pytest.raises(SystemExit) as exc:
        cli.main([flag, link], io.StringIO())

    assert exc.value.code == 2


def _classic_doubler_solution_link(cage_value: int) -> str:
    """A synthesised 4x4 doubler link mirroring ADR-0008's ChinStrap puzzle: a
    solved grid with four declared doublers (one per row/column/box, distinct
    digits) declared by a `Doubler` marker cage, and a cosmetic cage (type
    2001, graduated to a killer sum by its numeric value) over R1C1 (digit 3),
    the R1C2 doubler (digit 2, folded to 4), and R1C3 (digit 4). The folded sum
    is `3 + 2*2 + 4 = 11` — out of range for a plain 3-cell cage (max
    4+3+2=9), the case cosmetic cages exist for. The caller picks the declared
    total, so 11 solves and any other total breaks. The four doubler cells are
    left blank for the solver to fill; every other cell is a given, so the
    Latin constraints force them."""
    solution = [3, 2, 4, 1, 4, 1, 3, 2, 2, 3, 1, 4, 1, 4, 2, 3]
    doublers = sorted({1, 6, 11, 12})
    regions = [(i // 4 // 2) * 2 + (i % 4 // 2) for i in range(16)]
    cells: list[dict[str, object]] = [
        {} if i in doublers else {"given": True, "value": solution[i]}
        for i in range(16)
    ]
    puzzle = {
        "cells": cells,
        "size": 4,
        "constraints": [
            {"type": 0},
            {"type": 1, "regions": regions},
            {"type": 2001, "cages": [{"cells": [0, 1, 2], "value": str(cage_value)}]},
            {"name": "Doubler", "type": 2001, "cages": [{"cells": doublers}]},
        ],
    }
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle}
    payload = LZString.compressToEncodedURIComponent(json.dumps(doc))
    return f"https://sudokumaker.app/?puzzle={payload}"


def test_doubler_marker_folds_the_declared_doubler_into_the_cage_sum(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The Doubler marker cage declares the variant, so the CLI needs no flag —
    # the folded sum 3 + 2*2 + 4 = 11 solves.
    link = _classic_doubler_solution_link(cage_value=11)

    code = cli.main([link], io.StringIO())

    assert code == 0
    assert capsys.readouterr().out.split("\n")[0] == "found"


def test_a_wrong_declared_total_breaks_the_doubler_cage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The doubling is what closes the gap: a declared total other than the
    # folded 11 can't be met, so the link is broke.
    link = _classic_doubler_solution_link(cage_value=9)

    code = cli.main([link], io.StringIO())

    assert code == 1
    assert capsys.readouterr().out.split("\n")[0] == "broke"


def _classic_named_cage_link(name: str, cage_value: int) -> str:
    """A synthesised, fully-given classic 4x4 solution (the same 2x2-box grid
    as `_classic_doubler_solution_link`, no doublers) carrying a single `type
    2001` cosmetic cage over R1C1-R1C3 named `name`. `cage_value` is the
    cage's stored sum — 9 matches the solution's own R1C1+R1C2+R1C3."""
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


def test_unrecognized_named_cage_exits_two_with_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = _classic_named_cage_link("Foobar", cage_value=9)

    code = cli.main([link], io.StringIO())

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "Foobar" in captured.err


def test_ignore_unknown_named_cages_flag_strips_and_honors_the_cage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = _classic_named_cage_link("Foobar", cage_value=9)

    code = cli.main(["--ignore-unknown-named-cages", link], io.StringIO())

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
