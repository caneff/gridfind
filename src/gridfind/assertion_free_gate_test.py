"""No test in this repo may be unable to fail.

The check is test-audit's `--gate` mode, run here as an ordinary pytest test so
it rides `just check` -> `uv run pytest` and needs no recipe of its own. Only
smell 1 (assertion-free) gates; run `python3 ~/.agents/skills/test-audit/audit.py .`
by hand for test-audit's other four smells, which stay advisory.

Two things the gate cannot do for itself, so they are done here:

- **The roots are named, not inherited.** `--gate` walks a directory tree, not
  git, pruning only dot-dirs and a fixed excluded-dirs list — so a gitignored
  non-dot directory in the worktree (`graft/`) is scanned, and a stray hollow
  `.py` under one would fail the build over a file the repo does not contain.
  `ROOTS` is every directory this repo keeps Python in; a new one belongs here.
- **A root that does not exist exits 0** (caneff/agent-skills#685), so a
  mis-derived path would leave this gate permanently and silently green.
  `test_the_gate_has_a_root_to_scan` fails in that case instead.

A non-zero exit means "found hollow tests" only when the run also named some;
non-zero with nothing on stdout is the audit itself crashing, and says so.
"""

import pathlib
import subprocess
import sys

import pytest

AUDIT = pathlib.Path.home() / ".agents" / "skills" / "test-audit" / "audit.py"
REPO = pathlib.Path(__file__).parents[2]
ROOTS = ("src", "scripts")


def test_the_gate_has_a_root_to_scan() -> None:
    missing = [root for root in ROOTS if not (REPO / root).is_dir()]
    assert not missing, (
        f"no such directory under {REPO}: {missing} — the gate would scan nothing"
    )


def test_no_test_in_this_repo_is_assertion_free() -> None:
    if not AUDIT.exists():
        pytest.skip(
            f"test-audit not installed at {AUDIT} — "
            "clone caneff/agent-skills to enable this gate"
        )

    for root in ROOTS:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell, trusted input
            [sys.executable, str(AUDIT), "--gate", str(REPO / root)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            continue
        assert result.stdout.strip(), (
            f"the assertion-free audit crashed on {root}/ — it checked nothing:\n"
            f"{result.stderr}"
        )
        pytest.fail(
            f"test-audit found tests that cannot fail under {root}/:\n"
            f"{result.stdout}"
            "A test with no assertion proves nothing. Give each one a real check, "
            "or delete it."
        )
