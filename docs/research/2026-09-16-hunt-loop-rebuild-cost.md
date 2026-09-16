# Hunt-loop build-vs-solve cost, and ADR-0002's revisit trigger

caneff/gridfind#795, part of caneff/sudokumaker-custom-constraints#478.

## Question

ADR-0002 (`docs/adr/0002-no-puzzle-reuse-api.md`) rejected a build-once/
solve-many API: on a classic 9×9, `build_engine` measured ~0.36 ms against a
34.8 ms empty-board `verdict`, ~1% of wall time, and no caller raced many
working states over one fixed puzzle. Its revisit trigger needs *both* an
interactive hunt loop landing **and** profiling showing the build is a
material share, which needs a much larger model or a much cheaper solve than
that ~1%. This asks: on a realistic hunt-shaped loop — many checks against
one fixed puzzle, pins differing per check, including a near-broke /
uniqueness-style check like the one `finders/ghosts/minimal.py` runs — what
is that share today, and does `CpModel.clone()` reuse change it materially?

## Method

Worktree: `research/795-rebuild-cost` off `origin/main` in a separate
`gridfind-wt-795` checkout, never the primary checkout. Probe script:
`.scratch/bench_rebuild_cost.py` (git-ignored, not committed).

- **Puzzle**: a 9×9 board with a layered constraint set closer to a real
  finder's model than a bare classic grid — `sudoku` + one `thermo` + one
  `arrow` + two `cage` clues (five constraints), plus a "heavy" variant with
  20 more 2-cell `cage` clues tiled across the board (25 constraints total),
  to test whether more constraints move the build share.
- **Checks**: 30 per run, modeled on the shape `finders/ghosts/minimal.py`
  actually runs (many CP-SAT checks against one fixed puzzle, differing pins,
  read directly from gridfind's `build_stack`/`build_engine`/`applier`
  rather than `verdict()` — see below):
  - 24 "easy" checks: one placement pin per check (most consistent with a
    fixed solution grid → `found`; every 4th contradicts it → `broke`), the
    everyday shape of a hunt probing one cell at a time.
  - 6 "hard" checks: forbid the known solution grid entirely (`some cell
    differs`) and ask whether anything else remains — the uniqueness-style,
    near-broke check `minimal.py`'s `unique()` runs, reified the same way
    (`reify_holds` + `add_bool_or` over the negated indicators).
  - Given counts tried: 28 (typical solved-sudoku clue count) and 20 (fewer
    givens → larger search space for the hard checks).
- **Two build strategies**, each timed separately for build/clone/pin vs.
  solve:
  - **rebuild-per-check** — what `verdict()` does today: fresh
    `build_stack` + `build_engine` + `apply` every check.
  - **clone-reuse** — ADR-0002's "known mechanism if ever needed": build the
    base engine once, then `CpModel.clone()` per check and pin that check's
    state directly on the clone via `get_int_var_from_proto_index` (looked
    up by proto index recorded from the base build).
- **Single-threaded, on purpose**: `gridfind.verdict._build_and_solve`
  hardcodes `solver.parameters.num_workers = 8` (`src/gridfind/verdict.py:73`)
  — there is no way to get `verdict()` itself down to 1 worker, so this probe
  bypasses `verdict()` and calls `build_stack`/`build_engine`/`apply`
  directly, setting `num_workers = 1` on its own `CpSolver` instances, per
  the box rule. Numbers below are therefore *not* directly comparable to
  ADR-0002's own 34.8 ms figure, which almost certainly ran with the
  library's parallel default — see Caveats.
- `uptime` checked before each run (load average 3–5 on a 32-core box,
  single-threaded solves); each run completed in a few seconds, well under
  the 10-minute budget.

## Results

All times ms, summed over 30 checks unless noted. ortools 9.15.6755.

| config | build (rebuild) | solve (rebuild) | build share | clone+pin (reuse) | solve (reuse) | reuse overhead share | speedup | time saved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 28 givens, 5 constraints | 34.1 | 260.1 | 11.59% | 13.4 (+0.996 base) | 261.3 | 5.22% | 1.067x | 18.5 ms |
| 20 givens, 5 constraints | 33.0 | 305.6 | 9.75% | 12.8 (+0.871 base) | 310.1 | 4.20% | 1.046x | 14.9 ms |
| 28 givens, 25 constraints (heavy) | 30.4 | 250.0 | 10.83% | 10.1 (+0.739 base) | 249.8 | 4.13% | 1.076x | 19.8 ms |

Per-check medians (rebuild path): build 0.85–0.94 ms, solve 9.3–11.3 ms —
every check in this run, easy and hard alike, solved in single-digit-to-low-
double-digit milliseconds; none of the six near-broke checks per run ground
toward the 10 s budget. The heavy 25-constraint variant did not measurably
grow build time over the 5-constraint one (both ~1 ms/check) — cage/thermo/
arrow rule emission on this puzzle size is cheap regardless of constraint
count; only a much bigger jump in model size would be expected to move it.

Raw output: `.scratch/bench_output.txt`, `.scratch/bench_output_20givens.txt`,
`.scratch/bench_output_heavy.txt` (git-ignored, not committed — rerun
`.scratch/bench_rebuild_cost.py [n_givens] [heavy]` to reproduce).

## Verdict on ADR-0002's revisit trigger

**Not met**, on both of the ADR's own conjunctive conditions:

1. **A material build share, from a much larger model or a much cheaper
   solve than ~1%.** Measured share is ~10–12%, an order of magnitude above
   the ADR's ~1% baseline — but that's from the solve being cheap (checks in
   this puzzle size solve in ~10 ms even for the near-broke case), not from
   the model growing large: quintupling the constraint count (5 → 25) left
   per-check build time flat (~1 ms). So "material" only in the relative
   sense the ADR itself anticipated ("35 ms is the easy case... shrinking the
   build's share further" cuts the other way here — these are *all* easy-ish
   cases by the ADR's own yardstick). At today's build cost (~1 ms/check),
   `clone()` reuse recovers only ~0.5–0.7 ms/check net (clone + pin minus the
   avoided rebuild), which is 15–20 ms saved across 30 checks — real, but not
   the order-of-magnitude win a "much larger model" would produce.
2. **An interactive hunt loop that actually lands on gridfind.** It hasn't.
   `finders/ghosts/minimal.py`'s `unique()` loop is exactly the shape this
   probe modeled — many checks, one fixed puzzle, differing pins, a
   near-broke uniqueness check via `sufficient_assumptions_for_infeasibility`
   — but it hand-rolls its own `cp_model.CpModel`, not gridfind's
   `build_stack`/`build_engine`/`verdict()`. No finder in this repo drives
   gridfind's engine in a loop today (per the wayfinder map,
   caneff/sudokumaker-custom-constraints#478, that's still "not yet
   specified" — which hunt pilots the finders-on-gridfind spec).

So: the build's *relative* share is higher than the ADR's number once
solves are this cheap, but nothing today exercises it, and the absolute
saving on offer (sub-millisecond per check) doesn't clear the bar the ADR set
for reopening the decision. Revisit when a real hunt loop lands on gridfind's
engine and its checks are this cheap in practice — at that point `clone()`
reuse (verified workable here via `CpModel.clone()` +
`get_int_var_from_proto_index`) is still the right mechanism, per ADR-0002
decision 3.

## Caveats

- **Not directly comparable to ADR-0002's own numbers.** `verdict()`
  hardcodes 8 workers; this probe used 1 (box rule), and reached gridfind's
  build/apply pipeline directly rather than through `verdict()` to make that
  possible. Multi-threaded solves would very likely be faster in wall time
  (more search bandwidth) while build stays single-threaded-cost regardless,
  which would *raise* the build's share further under the box's forced
  single-worker probing — i.e. this probe's build-share numbers are an
  upper-ish bound relative to what `verdict()`'s own 8-worker solves would
  show, not a like-for-like re-measurement of the ADR's table.
- **The near-broke checks here weren't actually near the 10 s time limit.**
  On this puzzle size (9×9, ≤25 light constraints, 20–28 givens) CP-SAT
  proves non-existence of a second solution in single-digit milliseconds.
  A genuinely hard uniqueness check (larger board, tighter near-minimal clue
  set, or a harder constraint mix) would grind longer and shrink the build's
  share further, the direction ADR-0002 already predicted — this probe did
  not find a puzzle shape in the time budget where the near-broke case
  dominated wall time the way a truly hard hunt target would.
- **Constraint-count scaling wasn't pushed hard.** 5 → 25 constraints (all
  small cages) didn't move build time; a model an order of magnitude larger
  in cell/rule count (not just constraint *count*) might behave differently
  and wasn't tested here — that's the actual "much larger model" case the
  ADR's trigger names, and this probe only tested a modest constraint-count
  increase, not a modest model-size increase.
- `clone()` + `get_int_var_from_proto_index` is confirmed to work on this
  ortools version (9.15.6755) for pinning per-check state on a cloned model
  without rebuilding — the mechanism ADR-0002 decision 3 names as available
  if needed is, in fact, available.
