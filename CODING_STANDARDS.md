# Coding standards

The rules a change must satisfy. A reviewer (human or Sandcastle) loads this
file to judge a diff. The gate (`just check`) enforces the mechanical parts;
this doc covers the parts a linter can't.

## Tooling is law

- **uv** for everything. No `pip`, no `poetry`, no `python -m venv` by hand.
- **ruff** lints + formats; **ty** type-checks. If `just check` is red, the
  change is not done. Don't `--no-verify` or add blanket `# noqa` / `# ty: ignore`
  to silence a real finding — fix it, or narrow the suppression with a reason.

## Types

- Annotate everything, everywhere — not just the public surface. Internal
  helpers, test functions, and test helpers all carry annotations too. `ANN`
  runs on `*_test.py` as well (only `S101`, the assert rule, is relaxed there),
  so a bare `def test_...():` is a lint failure — write `def test_...() -> None:`.
- Public functions and methods carry annotations (ruff `ANN` enforces presence;
  ty checks them). ty is gradual — it won't demand annotations, so `ANN` is what
  forces them. Don't leave public signatures inferred.
- Prefer precise types over `Any`. Reach for `Any` only at genuine boundaries,
  and say why.
- `X` (capital) is allowed for feature matrices — that's why `N803`/`N806` are
  off. Don't abuse the exception for ordinary variables.

## Tests

- Test files are **`*_test.py`**, interleaved next to the code they test.
- Test **behavior**, not implementation. A test that only restates the code is
  noise.
- **No assertion-free tests.** A test that exercises code without asserting an
  observable outcome is worse than no test — it inflates coverage and proves
  nothing. Coverage is a soft signal; a green bar with hollow tests is a lie.
- Use **hypothesis** for numeric / edge-heavy logic (parsers, transforms,
  anything with a range of valid inputs) — it finds the cases you won't enumerate.
- Prefer **`@pytest.mark.parametrize`** where it makes sense: when several tests
  share one body and differ only by data (inputs and expected outcomes), fold
  them into one parametrized test with a named `id` per case, rather than copying
  the body. "Where it makes sense" is the limit — don't force unrelated cases
  together, don't parametrize when each case needs its own distinct assertions or
  a descriptive name that carries real meaning, and prefer an assert helper over
  a cross-cutting parametrize when a known upcoming file split would fight it.
- Markers must be registered (pytest runs `--strict-markers`). An `xfail` that
  passes is a failure (`xfail_strict`) — remove the marker when the bug is fixed.
- When writing or reviewing tests, run the `python-testing-patterns` skill's
  critical-eye pass — behavior ownership, duplicate coverage, brittle string
  matching, overbroad fixtures, unit-vs-integration boundaries — before adding
  assertions.

## Style

- Boring over clever. The reader at 3am wins.
- pathlib over `os.path` (ruff `PTH`). Don't shadow builtins (`A`).
- Keep public API surface small and typed — downstream agents type-check
  against it via `py.typed`.
- **Import the module, not its functions, when the prefix carries meaning.**
  Write `json.loads`, `os.path.join`, `np.array` — the namespace tells the
  reader where the name comes from, and reads the same at every call site.
  Reach for `from module import name` only when the origin is obvious and the
  prefix would be noise (`from dataclasses import dataclass`), or when one
  module supplies many names used throughout the file. Never strip a
  meaningful prefix just to shorten one line — a bare `loads` or `connect`
  hides its source and collides with the next module that exports the same
  name.

## Comments describe the code, not its history

A comment or docstring speaks to the reader in front of the current code, not
to the reviewer of the diff that produced it. Write what the code *does* and
*why*; never what it *used to do*.

- **No history narration.** Cut the diff-against-a-version-nobody-can-see:
  "used to raise," "is retired," "no longer," "replacing the scalar X," "split
  out of Y," "byte-identical to before," "exactly as before," "has always
  emitted," "no-regression." The reader never saw the old code, so the
  comparison lands as noise. Git already holds that story with the diff
  attached; a comment that repeats it does the job worse.
- **State the invariant, not the change.** "A cage with no `schrodinger` layer
  sums each cell's sole content variable" earns its place; "keeps summing…
  byte-identical to before" does not. Same fact, minus the backward glance.
- **Cite the durable doc, not the closed ticket.** A citation earns its place
  only when a reader would open it and find *more* than the comment already
  says. That test passes for the in-repo design record — `ADR-NNNN`
  (`docs/adr/`), `CONTEXT.md`, `(map #1, decision N)` — which points forward to
  reasoning that still lives somewhere navigable. It fails for a bare
  `(issue #NNN)` trailer: the issue closed when the work merged, its conclusion
  is already in the code and the comment beside it, and the number just
  duplicates what `git blame` gives for free. So write `(ADR-0004)`, not
  `(issue #157)`. A bare `spec #NNN` / `decision #N` trailer is the same
  closed-ticket duplication — collapse it into the `ADR-NNNN` that records the
  decision, or cut it if it only restates the code beside it. Keep an
  `issue #`/`spec #` cite only where the sentence explicitly sends the reader
  there for something not restated — "the full field map is in
  `docs/research/sudoku-link-formats.md` §4a." A changelog of merge order
  ("202 first, 301 next, 200 after") is never a citation; cut it.
- **When you change code, delete the comment that describes the old shape.**
  A stale comment is worse than none — it actively lies. If the edit made a
  docstring's claim false, fix the docstring in the same diff.

## Architecture

- **One home per behavior — no parallel implementations.** When two call sites
  need the same decode, walk, lookup, or assembly, route both through one shared
  seam; do not hand-roll a second copy that reads the same data a different way.
  A parallel implementation drifts silently: a fix or new constraint lands in
  one copy, the other keeps the old behavior, and the two verdicts disagree on
  the same puzzle with nothing red to show it. This is the repo's dominant
  refactor — killer cages, the edge-clue decoders, `decode_cell`/`write_cell`,
  the decoder registry, the region-map resolver, the active/inert predicate, and
  witness assembly were each collapsed to a single home after a second copy
  appeared.
- **`__init__.py` is wiring only — no `def` or `class` in it.** A package's
  `__init__` holds the package docstring, the submodule imports, and the
  `__all__` re-export list. Nothing else. Python lets you define real code
  there, but a responsibility that lives in `__init__` has no named home: it
  gets no module of its own, and its tests have nowhere natural to sit beside.
  Give every behavior a named module (`decode.py`, `registry.py`, …) and let
  `__init__` assemble the public surface from them.
- **Unknown or unmodeled input fails loud — warn to stderr or raise, never
  drop silently.** An unrecognized flag, layer name, or constraint payload means
  the code's model of the link is incomplete, and a silent skip turns that into
  a wrong verdict the caller cannot see. Reject a genuinely unknown name
  (`UnknownLayerError`); for a constraint the engine cannot yet model but the
  link legitimately carries, drop it with a stderr warning
  (`_warn_on_dropped_constraints`, `_warn_dropped_negative`) so the run
  continues but the gap is visible. Silence is the one forbidden response.
