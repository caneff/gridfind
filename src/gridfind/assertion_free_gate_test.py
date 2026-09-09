"""The assertion-free gate: no test in this repo may be unable to fail.

Rides `just check`'s existing `uv run pytest` rather than adding a second gate
recipe -- test-audit's `--gate` mode is just another test from pytest's point
of view, so it needs no wiring in the justfile at all (issue #792, worked
example caneff/sudokupad-art#88).

Only smell 1 gates. test-audit's other four smells (tautology, mock-the-world,
interaction-only, empty/skipped) stay report-only: those tests still fail when
the behavior breaks, so blocking a merge on one costs more than it buys. Run
`python3 ~/.agents/skills/test-audit/audit.py .` by hand for the full report.

`--gate` exits 0 on a root that does not exist (caneff/agent-skills#685), which
would leave this gate permanently and silently green on a typo'd path. Hence
`test_the_gate_is_pointed_at_this_repo` below: the root is checked for markers
only this repo has, so a mis-derived path fails here instead of passing there.
"""

import pathlib
import subprocess
import sys

import pytest

AUDIT = pathlib.Path.home() / ".agents" / "skills" / "test-audit" / "audit.py"
REPO = pathlib.Path(__file__).parents[2]


def test_the_gate_is_pointed_at_this_repo() -> None:
    assert (REPO / "pyproject.toml").is_file(), f"{REPO} is not the gridfind root"
    assert (REPO / "src" / "gridfind" / "engine.py").is_file(), (
        f"{REPO} is not the gridfind root"
    )


def test_no_test_in_this_repo_is_assertion_free() -> None:
    if not AUDIT.exists():
        pytest.skip(
            f"test-audit not installed at {AUDIT} — "
            "clone caneff/agent-skills to enable this gate"
        )

    result = subprocess.run(  # noqa: S603 — fixed argv, no shell, trusted input
        [sys.executable, str(AUDIT), "--gate", str(REPO)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "test-audit found tests that cannot fail:\n"
        f"{result.stdout}{result.stderr}"
        "\nA test with no assertion proves nothing. Give each one a real check, "
        "or delete it."
    )
