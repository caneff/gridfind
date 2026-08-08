# ADR-0002: `verdict` rebuilds per call — no build-once/race-many API

- **Status:** Accepted
- **Date:** 2026-08-08
- **Decides:** whether `verdict` should expose a reusable "pin one puzzle, race
  many working states" surface (raised by an architecture-deepening review of
  the `verdict` seam).

## Context

`verdict.py`'s module docstring promised puzzle reuse:

> Pinning one puzzle and racing many working states reuses the puzzle value —
> no new API.

The code does not honor that: every `verdict(puzzle, working_state)` call
re-resolves the puzzle's records, rebuilds the engine, and re-emits every rule
before applying the working state. The promise invites a future reader to build
a `build(puzzle) -> BuiltPuzzle` / `built.verdict(state)` surface so the
expensive build happens once.

Two facts decide against it.

**No caller races many states on one puzzle.** The corpus is a set of distinct
`{puzzle, working_state}` pairs — each a different puzzle, not many states over
one. The CLI is one document in, one verdict out. gridfind runs
pure-satisfaction with no enumeration, so no search races states either. The
one scenario that *would* reuse — an interactive "have I broken it yet?" loop
after every placement on a fixed puzzle — is gridfind's stated purpose but is
not implemented anywhere today.

**The build is ~1% of a solve.** Measured on a classic 9×9 (ortools 9.15):

| step | cost |
| --- | --- |
| `build_engine` (resolve records + emit rules) | 0.36 ms |
| full `verdict` (build + solve, empty board → found) | 34.8 ms |
| `CpModel.clone()` | 0.11 ms |

Reuse via `clone()` would save ~0.25 ms against a 35 ms race — and 35 ms is the
easy case; a near-broke state grinds toward the 10 s limit, shrinking the
build's share further. Even a 100-check interactive session spends ~36 ms
rebuilding against ~3.5 s solving.

A public build-once/race-many surface is therefore flexibility with no caller
and no measurable payoff — a speculative seam that would leak whatever the
reusable base turns out to be into every caller's hands.

## Decision

1. **No build-once/race-many public API.** `verdict(puzzle, working_state)`
   stays the one seam and rebuilds the engine per call.

2. **Correct the docstring.** Drop the reuse claim rather than build the API to
   honor it. The docstring should describe what the code does — rebuild per
   call — not an aspiration no caller exercises.

3. **The mechanism is known if it is ever needed.** `CpModel.clone()` exists and
   is verified: build a base model once (board + layers + givens), then
   `base.clone()` per race and add that state's pins. Cloning — not solver
   assumptions — is the right tool, because each race pins a *different* set of
   cells, and assumptions fit a fixed constraint set toggled on and off.

## When to revisit

Build a reusable surface when a concrete trigger appears:

- an interactive loop lands that races many working states against one fixed
  puzzle, **and**
- profiling shows the per-call build is a material share of that loop's time —
  which requires either a much larger model or a much cheaper solve than today's
  ~1%.

Until both hold, `verdict` rebuilds per call.
