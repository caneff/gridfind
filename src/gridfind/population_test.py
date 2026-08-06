"""By-construction populations: a working state whose verdict is known by
its filename (`found-*` / `broke-*`), asserted through `verdict(...)` only
(spec #4, decisions 36-37).

Puzzles are discovered by glob, not by a hand-maintained directory-to-stack
mapping — each file's own `stack:` header is the single source of truth for
its stack (issue #38, decisions #33-#34). A case's canonical identity (and
its pytest id) is the expanded, alphabetically-sorted, `+`-joined layer list,
so a preset and its explicit spelling collapse to the same id.
"""

from pathlib import Path

import pytest

from gridfind.layers import expand_stack
from gridfind.verdict import verdict
from gridfind.working_state import parse

POPULATIONS_DIR = Path(__file__).parent / "populations"


def _population_cases() -> list[tuple[list[str], Path]]:
    return [
        (sorted(expand_stack(parse(path.read_text()).stack)), path)
        for path in sorted(POPULATIONS_DIR.rglob("*.txt"))
    ]


_CASES = _population_cases()


@pytest.mark.parametrize(
    ("stack", "path"),
    _CASES,
    ids=[f"{'+'.join(stack)}/{path.stem}" for stack, path in _CASES],
)
def test_population_matches_its_filename_verdict(stack: list[str], path: Path) -> None:
    expected_kind, _, _ = path.stem.partition("-")
    assert expected_kind in ("found", "broke")

    result = verdict(stack, path.read_text())

    assert result.kind == expected_kind
