"""No test in this repo may be unable to fail.

The check is test-audit's `--gate` mode, run here as an ordinary pytest test so
it rides `just check` -> `uv run pytest` and needs no recipe of its own. Only
smell 1 (assertion-free) gates; run `python3 ~/.agents/skills/test-audit/audit.py .`
by hand for test-audit's other four smells, which stay advisory.

Three things the audit cannot do for itself, so they are done here:

- **The roots come from `pyproject.toml`.** `--gate` walks a directory tree,
  not git, pruning only dot-dirs and a fixed excluded-dirs list — so a
  gitignored non-dot directory in the worktree (`graft/`) is scanned, and a
  stray hollow `.py` under one would fail the build over a file the repo does
  not contain. The roots are therefore named rather than inherited, and named
  once: `[tool.ty.environment] root` is already the repo's declaration of where
  its Python lives, so a directory added there is gated without a second edit.
- **A root that does not exist exits 0** (caneff/agent-skills#685, open), so a
  mis-derived path would leave this gate permanently and silently green.
  `test_the_gate_has_a_root_to_scan` fails in that case instead.
- **A `--gate` that stopped existing also exits 0.** `audit.py` matches the
  flag positionally and otherwise falls through to its report mode, which
  exits 0 whatever it finds; an upstream rename would silently retire this
  gate. `test_the_audit_still_catches_a_hollow_test` is the positive control —
  it feeds the audit a test it must reject, so the gate is seen red on every
  run and a green build means the check really ran.

A non-zero exit means "found hollow tests" only when the run also named some;
non-zero with nothing on stdout is the audit itself crashing, and says so.
"""

import pathlib
import subprocess
import sys
import tomllib

import pytest

AUDIT = pathlib.Path.home() / ".agents" / "skills" / "test-audit" / "audit.py"
REPO = pathlib.Path(__file__).parents[1]
HOLLOW = "def test_a_hollow_specimen():\n    compute()\n"


def _roots() -> list[str]:
    """The repo's Python roots, as `pyproject.toml` already declares them."""
    with (REPO / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)
    declared = config["tool"]["ty"]["environment"]["root"]
    return [root.removeprefix("./") for root in declared]


def _gate(root: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell, trusted input
        [sys.executable, str(AUDIT), "--gate", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _require_audit() -> None:
    if not AUDIT.exists():
        pytest.skip(
            f"test-audit not installed at {AUDIT} — "
            "clone caneff/agent-skills to enable this gate"
        )


def test_the_gate_has_a_root_to_scan() -> None:
    missing = [root for root in _roots() if not (REPO / root).is_dir()]
    assert not missing, (
        f"no such directory under {REPO}: {missing} — the gate would scan nothing"
    )


def test_the_audit_still_catches_a_hollow_test(tmp_path: pathlib.Path) -> None:
    _require_audit()
    (tmp_path / "specimen_test.py").write_text(HOLLOW)

    result = _gate(tmp_path)

    assert result.returncode != 0, (
        f"the audit passed a test with no assertion — `--gate` is no longer "
        f"gating, so the check below proves nothing:\n{result.stdout}{result.stderr}"
    )
    assert "specimen_test.py" in result.stdout, (
        f"the audit failed without naming the hollow test it found:\n"
        f"{result.stdout}{result.stderr}"
    )


def test_no_test_in_this_repo_is_assertion_free() -> None:
    _require_audit()

    for root in _roots():
        result = _gate(REPO / root)
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
