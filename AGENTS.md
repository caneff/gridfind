# gridfind — agent guide

Grid-puzzle constraint solving and validation: given a partly-built grid puzzle, decide **found** / **broke** / **unknown** and return a completion or near-miss. CP-SAT engine (OR-Tools), Python only.

## Commands

- **Full gate — run before calling any task done:** `just check`
- Test: `uv run pytest`
- Type check: `uv run ty check`
- Lint + format: `just fmt`
- **Real-link E2E suite** (on demand, not part of `just check`): `just e2e` — drives real SudokuMaker links from `src/gridfind/links/` through the CLI front door (`cli.main`); slow (CP-SAT) so it's deselected from the default run.

## Where things are

- Coding + testing standards → [`CODING_STANDARDS.md`](CODING_STANDARDS.md)
- Domain / context → `CONTEXT.md` (see `docs/agents/` for consumer rules)
- Source: `src/gridfind/`; tests are interleaved as `*_test.py` next to the code
- **Debugging a SudokuMaker link** (why it rejects, what constraints it carries) → `uv run python scripts/inspect_link.py '<link>' ...` — decodes and classifies each constraint (known/disabled/active/inert) and prints the verdict, one line per link. Reach for this instead of hand-rolling a decode probe.

## Conventions (summary — full rules in CODING_STANDARDS.md)

- Package manager is **uv**. Never `pip` or `poetry`.
- Type checker is **ty**, linter/formatter is **ruff** — both gate CI.
- Test files use the **`*_test.py`** suffix, never `test_*.py`.

## Design reasoning

- **Argue design calls on merits, never on "no puzzle uses it."** The supported puzzle/link set is small and grows on demand, so "no existing puzzle needs X" is circular — unsupported ≠ unneeded. Justify a scope, deferral, or modeling call by model coherence, code cost, or domain semantics instead. Dropping this crutch has flipped calls: forbidding a doubled S-cell costs an extra constraint; allowing it costs nothing, since `d0` is well-defined for both.

## Agent skills

### Issue tracker

Issues and specs live as GitHub issues (`gh` CLI) in `caneff/gridfind`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
