# Commands

The runnable checks and workflows for working in gridfind.

- **Full gate — run before calling any task done:** `just check`
- Test: `uv run pytest`
- **Assertion-free gate** (part of `uv run pytest`, so part of `just check`):
  a test with no assertion fails the build. Needs `caneff/agent-skills` checked
  out at `~/.agents/skills/test-audit/`; without it the gate skips and `-ra` (on
  by default) prints the reason. The other four test-audit smells stay advisory:
  `python3 ~/.agents/skills/test-audit/audit.py .` for the full report. Why the
  gate is shaped the way it is — `scripts/assertion_free_gate_test.py`.
- Type check: `uv run ty check`
- Lint + format: `just fmt`
- **Real-link E2E suite** (on demand, not part of `just check`): `just e2e` — drives real SudokuMaker links from `src/gridfind/links/` through the CLI front door (`cli.main`); slow (CP-SAT) so it's deselected from the default run.
