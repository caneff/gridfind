"""By-construction populations: a working state whose verdict is known by
its filename (`found-*` / `broke-*`), asserted through `verdict(...)` only
(spec #4, decisions 36-37).
"""

from pathlib import Path

import pytest

from gridfind.verdict import verdict

BOARD_POPULATION_DIR = Path(__file__).parent / "populations" / "board"


def _board_population_files() -> list[Path]:
    return sorted(BOARD_POPULATION_DIR.glob("*.txt"))


@pytest.mark.parametrize("path", _board_population_files(), ids=lambda p: p.stem)
def test_board_population_matches_its_filename_verdict(path: Path) -> None:
    expected_kind, _, _ = path.stem.partition("-")
    assert expected_kind in ("found", "broke")

    result = verdict(["board"], path.read_text())

    assert result.kind == expected_kind
