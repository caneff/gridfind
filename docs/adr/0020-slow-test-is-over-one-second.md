# ADR-0020: a `slow` test is one whose solve reliably costs over a second; `slow` and `e2e` run nightly

- **Status:** Accepted
- **Date:** 2026-08-22
- **Decides:** what makes a test `slow`, how many test-speed buckets exist, and
  when the deselected buckets run. Records the decision grilled out on
  [#424](https://github.com/caneff/gridfind/issues/424), the follow-up to
  PR #419 (#393) that first added the `slow` marker.

## Context

PR #419 added a `slow` pytest marker and a `just slow` recipe, deselected from
the gate by `-m "not e2e and not slow"`. Its first member was the exhaustive
mixed-stack enumeration — the full 4×4 `sudoku + schrodinger + doubler` space,
17280 completions, about 3 seconds of CP-SAT. The marker existed, but nothing
decided what else belonged behind it.

Two directions pulled against each other. One: audit the gate for tests that
are secretly slow and inflate its time for coverage a maintainer would rather
run on demand. Two: find coverage the gate lacks because it would be too slow —
larger exhaustive enumerations, and the hypothesis property tests spec #389
calls for.

A measurement pass settled the facts. The gate runs about 11 seconds, and no
single test in it exceeds ~0.5 seconds. The data has a clean gap: every gate
test is at or below 0.5s, and the only tests above a second are the two already
marked `slow` (the 17280 enumeration at 3.07s and the kropki-negative
doubler case at 1.65s). The property tests that #389 frames as "planned" are
already written and already in the gate, at about 0.09 seconds each.

## Decision

1. **Criterion — wall time, one rule.** A test is `slow` when its solve
   *reliably* costs more than **1 second** on a normal developer machine. Wall
   time is the only rule. "Exhaustive" or "property-based" describes a test; it
   does not mark it. Flakiness is never a reason to mark a test `slow` — a test
   that returns `unknown` under load is a bug to fix (raise its `time_limit_s`,
   or shrink the case), not a test to hide.

2. **One `slow` bucket.** A threshold rule makes a separate `property` marker
   redundant: a property test is `slow` only when it crosses the same second,
   and then it belongs with every other slow solve. `e2e` stays its own axis —
   it marks a real SudokuMaker link through the front door or the library path,
   a different *kind* of test, not merely a slower one. Two axes total, `slow`
   and `e2e`, no third.

3. **Nightly cadence.** A scheduled CI job runs `just slow` and `just e2e` once
   a day. GitHub's own failed-run notification is the alarm; the workflow does
   not open an issue on failure. On-demand-only tests rot silently; a nightly
   run catches a regression within a day without taxing the fast gate.

## Consequences

- **The concrete audit came back empty.** No gate test crosses a second, so
  nothing moves out. The two `slow` members are correctly placed. The
  hypothesis property tests stay in the gate. This answers the open question
  from T4 (#394): its property tests file under the **default gate**, not
  `slow`.
- **The kropki-negative test keeps its mark on wall-time grounds.** Its
  `[doubler]` case is 1.65s, over the line. Its inline reason moves from the
  flakiness story to the wall-time one. The "returns `unknown` on a loaded
  runner" flake — it uses the 10-second default solver budget — becomes its own
  follow-up ticket, not a change folded in here.
- **`slow` and `e2e` no longer rot.** The nightly job runs them where nothing
  ran them before.
- **The rule travels with the marker.** It lives in the `slow` marker's own
  description in `pyproject.toml` and in `CODING_STANDARDS.md`, so the next
  author reads it instead of re-arguing it per test.
