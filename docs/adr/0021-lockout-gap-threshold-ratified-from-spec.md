# ADR-0021: the lockout line's minimum-gap threshold is `size // 2`, amended from a real 4x4 SudokuMaker link

- **Status:** Accepted
- **Date:** 2026-08-26
- **Amended:** 2026-08-26 — the threshold is `size // 2`, not `(size - 1) //
  2`: a real 4x4 SudokuMaker lockout link requires an endpoint gap of 2,
  where the original spec-derived formula gave 1
  (spec [#723](https://github.com/caneff/gridfind/issues/723), ticket
  [#724](https://github.com/caneff/gridfind/issues/724)). See "Amendment"
  below; the original ratification-without-a-real-link posture this ADR
  first recorded is kept for the record, not because it still holds.
- **Decides:** the minimum end-to-end gap a lockout line (wire type 407)
  enforces, and that this threshold ships ratified from the spec derivation and
  the synthesized corpus, without a captured real lockout link
  (spec [#672](https://github.com/caneff/gridfind/issues/672) /
  [#677](https://github.com/caneff/gridfind/issues/677), verify flag
  [#667](https://github.com/caneff/gridfind/issues/667)).

## Context

A **lockout line** reads broke when its two ends sit too close together, or
when an interior cell's value falls inside the closed end interval. "Too close"
is a minimum gap between the ends. Spec #672 derived that gap as
`(size - 1) // 2` — 4 on a 9x9, 2 on a 6x6, 1 on a 4x4 — computed from
`engine.board.size`, never read off the wire.

Issue #677 carried its own acceptance line, the build-time verify flag #667:
confirm the `(size - 1) // 2` threshold against a **captured real lockout link**
before ship. No real lockout link was captured. The found/broke corpus is
synthesized in code (`scripts/synthesize_lockout_links.py`), not exported from a
live SudokuMaker lockout puzzle.

The threshold is a semantic modeling constant, not a wire field. The wire
carries only the path's cell indices; the gap is computed from board size at the
`Line` layer. So a captured link would confirm the type-407 **decode shape** —
which #677's other acceptance criteria already cover — but not the gap constant,
which no wire ever carries.

## Decision

**Ratify `(size - 1) // 2` as the lockout minimum-gap threshold on the strength
of the spec #672 derivation and the synthesized found/broke corpus. A captured
real link is not a ship gate for this constant.**

1. **One home for the constant.** The threshold is `(engine.board.size - 1) // 2`,
   computed once in `layers.line._lockout` and read nowhere else.

2. **The corpus pins the boundary.** The synthesized found/broke pair sets the
   ends at the gap boundary, so a wrong constant turns the on-demand e2e suite
   red — the same guard every value-mode relation ships behind.

3. **Same posture as grouped-line.** Grouped-line's `groups` bitmask shape ships
   from SudokuMaker's own convention without a real `type 406` link to
   ground-truth it (a one-function swap if a real link corrects it). Lockout's
   gap constant takes that posture: shipped from convention, a one-constant swap
   in `_lockout` if a real link ever contradicts it.

## Consequences

- Issue #667's build-time verify is discharged by this ratification, recorded
  here. The lockout comment and `_lockout` docstring cite **ADR-0021**, not the
  closed issue number.
- If a real SudokuMaker lockout link later shows a different gap, the fix is a
  one-constant change in `layers.line._lockout` plus a corpus regen — no wire,
  decode, or predicate-shape change.

## Amendment (2026-08-26): the real link this ADR shipped without

Spec #723 (the eval-page review of 2026-08-26) records the real-link
observation this ADR's original Decision shipped without: on a 4x4 grid, a
SudokuMaker lockout line's two ends must differ by at least **2**, not the
1 that `(size - 1) // 2` computed.

`(size - 1) // 2` and the correct value agree everywhere the original
Decision actually checked (9x9 = 4, matching `9 // 2`), which is why the
synthesized corpus never caught the gap: both boundary fixtures sat on a
4x4 board that never existed until the real link did. The general formula
SudokuMaker implements is **`size // 2`** (equivalently `ceil((size - 1) /
2)`): 2 on 4x4, 3 on 6x6, 4 on 9x9 — one more than `(size - 1) // 2` on any
even board size, unchanged on any odd one.

### Amended decision

**The lockout minimum-gap threshold is `size // 2`, computed once in
`layers.line._lockout` from `engine.board.size` — same one home the original
Decision named, same posture (a modeling constant the wire never carries),
new value.** `found-lockout-4x4`/`broke-lockout-4x4` were rebuilt at the new
4x4 boundary (bulbs 1 and 3, gap exactly 2) so the corpus keeps pinning the
boundary the original Decision called for.

This ADR is amended, not replaced: the original Context and Decision above
record why the threshold shipped ratified from spec alone, and remain the
history of that choice. This amendment is the correction spec #723's real
link forced.
