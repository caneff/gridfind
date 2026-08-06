"""By-construction populations: a Puzzle + WorkingState whose verdict is known
by its filename (`found-*` / `broke-*`), asserted through `verdict(...)` only
(spec #4, decisions 36-37).

Each JSON case carries its own puzzle and working state — no hand-maintained
directory-to-stack mapping. A case's canonical identity (and its pytest id) is
the puzzle's expanded, alphabetically-sorted variant set (#47), so the sugar
spelling and the explicit spelling collapse to the same id.
"""

import json
from pathlib import Path

import pytest

from gridfind.layers import canonical_identity
from gridfind.puzzle import Puzzle, WorkingState
from gridfind.verdict import verdict

POPULATIONS_DIR = Path(__file__).parent / "populations"


def _load(path: Path) -> tuple[Puzzle, WorkingState]:
    doc = json.loads(path.read_text())
    puzzle = Puzzle.from_json(json.dumps(doc["puzzle"]))
    state = WorkingState.from_json(json.dumps(doc["working_state"]))
    return puzzle, state


def _population_cases() -> list[tuple[Puzzle, WorkingState, Path]]:
    return [(*_load(path), path) for path in sorted(POPULATIONS_DIR.rglob("*.json"))]


_CASES = _population_cases()


def _case_id(puzzle: Puzzle, path: Path) -> str:
    identity = "+".join(canonical_identity(puzzle.variants)) or "board"
    return f"{identity}/{path.stem}"


@pytest.mark.parametrize(
    ("puzzle", "state", "path"),
    _CASES,
    ids=[_case_id(puzzle, path) for puzzle, _, path in _CASES],
)
def test_population_matches_its_filename_verdict(
    puzzle: Puzzle, state: WorkingState, path: Path
) -> None:
    expected_kind, _, _ = path.stem.partition("-")
    assert expected_kind in ("found", "broke")

    result = verdict(puzzle, state)

    assert result.kind == expected_kind
