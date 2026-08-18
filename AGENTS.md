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
- **Building a test link** — corpus links under `src/gridfind/links/` are synthesized in code, never hand-authored on SudokuMaker.com: assemble a puzzle document and run it through `sudokumaker.document_to_link` (the exact reverse of `link_to_puzzle`). See `src/gridfind/cli_test.py` for the classic-Schrödinger synthesis pattern, and `scripts/synthesize_scell_links.py` (`main` regenerates the whole S-cell corpus) for the marking-case set.
- **Eyeball a branch's new eval links** ("show me the eval page") → `just eval-links --changed` in its worktree; open the printed localhost URL to review each new link's verdict by eye. **Never run this yourself as a background job** — the recipe binds a localhost server and serves forever, so a Claude-tracked Bash job reports "completed" the moment it binds and the harness reaps the server, killing the page. Hand the human `! just eval-links --changed &` — backgrounded in *their* shell (the trailing `&` is their shell's job, not a Claude-tracked bg job) so the URL prints and their prompt returns while the server keeps serving. If the URL scrolls past, the capture form is `! just eval-links --changed >/tmp/eval.log 2>&1 & sleep 1; cat /tmp/eval.log`.
- **Facing a new wire encoding, flag, or payload you don't yet model** → ask the human for an example link and decode it (`inspect_link.py`, or `link_to_document` for the raw block) **before** opening a research ticket. A real link is ground truth; the repo rarely documents wire encodings, so one example beats reading. It flipped #407: the kropki `negative` array read as a global on/off flag until a link showed `[1, 2, 4]` — a set of forbidden difference values.

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
