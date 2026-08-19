# Commands

The runnable checks and workflows for working in gridfind.

- **Full gate — run before calling any task done:** `just check`
- Test: `uv run pytest`
- Type check: `uv run ty check`
- Lint + format: `just fmt`
- **Real-link E2E suite** (on demand, not part of `just check`): `just e2e` — drives real SudokuMaker links from `src/gridfind/links/` through the CLI front door (`cli.main`); slow (CP-SAT) so it's deselected from the default run.
