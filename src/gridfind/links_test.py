"""On-demand E2E suite: real SudokuMaker links driven through `cli.main`, the
CLI front door (spec #185, issue #186).

Each case file under `links/` holds the argv `cli.main` receives: any flag
lines, then the link, one per line. Links are URL-encoded and carry no
spaces, so the loader builds argv by `content.split()`. The filename stem
starts `found-` or `broke-`; the loader partitions on the first `-` for the
expected verdict, exactly as `population_test.py` does for its
by-construction corpus.

A `found` case gets two layers of assertion: the front-door contract (exit
0, `found` on stdout, a grid follows), and an *independent* witness check —
`validate_witness` recovers the grid the CLI printed and checks it against
the `Puzzle` `decode_link` recovers from the same link, never calling
`verdict()` itself. A `broke` case trusts the curator's label: exit 1,
`broke` on stdout, nothing more (map #168 decision 2).

Deselected from the default run by `-m "not e2e"` in `pyproject.toml`'s
addopts; run on demand with `just e2e`.
"""

import io
from pathlib import Path

import pytest

from gridfind import cli
from gridfind.sudokumaker import decode_link
from gridfind.witness_validator import validate_witness

LINKS_DIR = Path(__file__).parent / "links"


def _link_cases() -> list[Path]:
    cases = sorted(LINKS_DIR.rglob("*.txt"))
    if not cases:
        # A glob that finds nothing must fail here. Left unchecked, an empty
        # list parametrizes into zero cases and the corpus passes by
        # vanishing (mirrors population_test.py's empty-corpus guard).
        msg = f"no link case files under {LINKS_DIR}"
        raise RuntimeError(msg)
    return cases


_CASES = _link_cases()


@pytest.mark.e2e
@pytest.mark.parametrize("path", _CASES, ids=[path.stem for path in _CASES])
def test_link_case_matches_its_filename_verdict(
    path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    expected_kind, _, _ = path.stem.partition("-")
    assert expected_kind in ("found", "broke")
    argv = path.read_text().split()

    code = cli.main(argv, io.StringIO())

    out = capsys.readouterr().out
    lines = out.split("\n")
    assert lines[0] == expected_kind

    if expected_kind == "found":
        assert code == 0
        link = argv[-1]
        puzzle, _ = decode_link(link, schrodinger="--schrodinger" in argv)
        assert validate_witness("\n".join(lines[1:]), puzzle)
    else:
        assert code == 1
