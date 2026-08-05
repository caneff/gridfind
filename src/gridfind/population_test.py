"""By-construction populations: a working state whose verdict is known by
its filename (`found-*` / `broke-*`), asserted through `verdict(...)` only
(spec #4, decisions 36-37).
"""

from pathlib import Path

import pytest

from gridfind.verdict import verdict

POPULATIONS_DIR = Path(__file__).parent / "populations"

STACKS_BY_DIRECTORY = {
    "board": ["board"],
    "board-rows-distinct": ["board", "rows-distinct"],
}


def _population_cases() -> list[tuple[list[str], Path]]:
    return [
        (stack, path)
        for directory, stack in STACKS_BY_DIRECTORY.items()
        for path in sorted((POPULATIONS_DIR / directory).glob("*.txt"))
    ]


@pytest.mark.parametrize(
    ("stack", "path"),
    _population_cases(),
    ids=[f"{'+'.join(stack)}/{path.stem}" for stack, path in _population_cases()],
)
def test_population_matches_its_filename_verdict(stack: list[str], path: Path) -> None:
    expected_kind, _, _ = path.stem.partition("-")
    assert expected_kind in ("found", "broke")

    result = verdict(stack, path.read_text())

    assert result.kind == expected_kind
