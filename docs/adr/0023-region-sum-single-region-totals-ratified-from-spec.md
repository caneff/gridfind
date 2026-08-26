# ADR-0023: region-sum's `singleRegionTotals` flag is ratified from spec, without a captured real link

- **Status:** Accepted
- **Date:** 2026-08-26
- **Decides:** that a region-sum line's `singleRegionTotals = false` means
  per-visit segment segmentation and `singleRegionTotals = true` names
  per-region pooling (unmodeled, refused loud), and that this decode fact
  ships ratified from spec #672 without a captured real type-404 link
  (spec [#672](https://github.com/caneff/gridfind/issues/672) /
  [#679](https://github.com/caneff/gridfind/issues/679), verify flag
  [#666](https://github.com/caneff/gridfind/issues/666)).

## Context

A **region-sum line** reads broke when its box-segments do not all add to the
same total. Spec #672 (via sub-map #400's #666) states the flag's meaning
directly: `singleRegionTotals = false` (the default) cuts a fresh segment
each time the line's `RegionMap` region changes along the ordered path — a
re-entered region is a **new** segment, never pooled with its earlier one —
and asserts those segment sums equal; `singleRegionTotals = true` would pool
every visit to one region into a single running total instead, a rule
gridfind does not model.

Issue #679 carried this forward as a build-time verify: confirm the
false/per-visit, true/per-region-pooling meaning against a captured real
link before ship. No real type-404 link was captured. The found/broke corpus
is synthesized in code (`scripts/synthesize_region_sum_links.py`), not
exported from a live SudokuMaker region-sum puzzle.

Unlike lockout's threshold (ADR-0021) or double-arrow's wire-type mapping
(ADR-0022), this fact is not a number or an assignment inferred from a
secondary source — it is spec #672's own explicit statement of what the flag
means, sourced from the line-clue sub-map's own research (#666). A captured
link would confirm the same per-visit segmentation the synthesized
region-re-entry fixture already exercises structurally; it would not add a
new fact the spec doesn't already state.

## Decision

**Ratify `singleRegionTotals = false` as per-visit segmentation and `true` as
unmodeled per-region pooling, on the strength of spec #672 and the
synthesized found/broke/re-entry corpus. A captured real link is not a ship
gate for this fact.**

1. **One home for the flag's meaning.** `layers.line._region_sum` is the only
   place `singleRegionTotals` is read; `true` raises `GridfindError` before
   any segmentation runs, `false` (or an absent key, defaulted at decode —
   `sudokumaker.line.region_sum_constraints`) drives the per-visit walk.

2. **The corpus pins the behavior.** The synthesized found/broke pair proves
   equal-vs-unequal segment sums on a box-tiled board; a unit-level fixture
   proves a re-entered region cuts a fresh segment rather than pooling with
   its earlier visit — so a wrong flag meaning (or a silently-passed `true`)
   turns a test red, the same guard every value-mode relation ships behind.

3. **Same posture as lockout (ADR-0021) and double-arrow (ADR-0022).** Each
   shipped a semantic or wire fact from spec/research and a synthesized
   corpus rather than blocking on a real capture, recording the ratification
   here so a later real link is a confirming (or correcting) swap, not a
   rebuild.

## Consequences

- Issue #666's build-time verify is discharged by this ratification, recorded
  here. The region-sum wire-type comment and `_region_sum` docstring cite
  **ADR-0023**, not the closed issue number.
- If a real SudokuMaker type-404 link later shows `singleRegionTotals = true`
  carrying a rule gridfind should model, the fix is teaching `_region_sum` a
  per-region-pooling branch instead of raising — no decode-shape or dispatch
  change.
