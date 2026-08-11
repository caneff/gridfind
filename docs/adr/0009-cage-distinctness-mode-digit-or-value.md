# ADR-0009: a cage's no-repeats mode is digit or value; a value is what the value methods say

- **Status:** Accepted
- **Date:** 2026-08-11
- **Decides:** what "distinct" means in a cage that holds a cell whose value is
  not its digit — a **doubler** or a **Schrödinger cell** — and where that value
  comes from (parent [#232](https://github.com/caneff/gridfind/issues/232),
  ticket [#236](https://github.com/caneff/gridfind/issues/236)).

## Context

A cage forbids its cells from repeating. Once a cell can be worth something other
than its face digit, "repeating" splits in two. A **doubler** showing 3 is worth
6. An **S-cell** holds two digits at once, say 2 and 3. So does a cage forbid a
repeated *digit* or a repeated *value*, and what is the value of a cell that
holds two digits?

ISS is no guide — it has no doublers, no modifiers, and no Schrödinger cells, so
its cage is a fixed digit-distinct `AllDifferent` with nothing to toggle.
gridfind carries all three, so it has a distinction ISS cannot express and must
resolve on model coherence alone.

## Decision

1. **A cage carries a `distinct-over` mode: `digit` (default) or `value`.** A
   **digits-distinct** cage forbids a repeated digit — today's rule, unchanged,
   and the classic killer convention, so every existing cage keeps its verdict.
   A **values-distinct** cage forbids a repeated value.

2. **Each layer reifies its own cell values into a channel; the cage only
   reads.** A cell's value is not the cage's to compute. Every layer that gives
   a cell a value beyond its digit reifies that value into a named channel: the
   doubler into `modifier_value` (`2·d0` on discovery), the Schrödinger layer
   into `s_value` (its two digits combined on `is_s`). A values-distinct cage
   reads each cell's value through `value_expr`, which returns whichever channel
   the cell has — else its raw digit — and puts them in one `add_all_different`.
   The cage never hand-rolls a `10·d0 + d1`; that would be a second, divergent
   definition of a value a layer already owns.

   Reading the value through the seam is the **default for every constraint that
   reads a cell**, not a cage specialty: a constraint takes a cell's *value*
   unless it has a specific reason to read raw digits. The digits-distinct
   no-repeats rule is that exception — the classic killer forbids a repeated
   placed *symbol*, so it reads digit slots directly (decision 1). The killer
   sum is a second, deliberate exception — see decision 6.

3. **Same value collides — always, with no exception.** Two cells clash exactly
   when their values are the same number. A doubler worth 18 and an S-cell that
   reads 18 collide, because a value is a number and 18 equals 18. There is no
   offset, no separate band, no rule that a "doubled 18" and a "concatenated 18"
   are different — they are the same value, so they repeat. An earlier draft
   proposed offsetting the two encodings apart; that was wrong, and it would have
   let two equal values sit in one cage.

4. **The Schrödinger layer builds each S-cell's value, and how it combines two
   digits is a puzzle-wide `combine` rule.** Since it is the layer that widens a
   cell to two digits, it is the layer that reifies the cell's value into the
   `s_value` channel — the same shape the doubler uses for `modifier_value`, so
   the cage reads a value without knowing which layer built it. Whether two
   digits combine by `sum` (2 + 3 = 5) or `concat` (2, 3 → 23) is the `combine`
   rule, a property of the whole puzzle that this layer holds, not the cage or
   the cell.

5. **A doubled S-cell stays deferred.** A cell that is both a doubler and an
   S-cell has no defined value yet — no link can encode both marks (they share
   the red color bit, ADR-0008) and nothing models the combination. Such a cell
   sits in both value channels at once, so `value_expr` raises rather than pick
   one — the unconstructable state fails loudly instead of silently mis-valuing
   the cell. The combination arrives with the rest of doubler-plus-S-cell
   coexistence, not here.

6. **Superseded — the killer sum no longer lives on the cage.** This decision
   originally had the cage's own sum read `value_expr` — a doubler's `2·d0`,
   an S-cell's combined `s_value` — so it shared the values-distinct half's
   value-seam reading rather than a private encoding. The killer cage later
   recomposed as `cage` (uniqueness) plus `group-sum` (the total), two
   constraints over the same cells, not one bundled layer (spec #240, issue
   #243). `group-sum` folds a modifier's `modifier_value` (ADR-0008 decision 4)
   but is **S-blind by its own, separate decision**: it raises "not
   Schrödinger-ready yet" over a named S-cell rather than reading `s_value`,
   so decision 6's value-seam reading for an S-cell no longer holds anywhere
   — the cage states no sum to hold it, and `group-sum` never reaches an
   S-cell's value at all. `distinct-over` still answers only for the cage's
   own no-repeats half, which is unaffected by this recomposition.

7. **`distinct-over` is an internal param with no decoder yet.** No SudokuMaker
   link we have carries a distinctness mode. The cage constraint accepts the key
   (its params are an open dict) and defaults to `digit`; the wire decoder stays
   untouched until a real values-distinct link shows which bit carries the mode.

## Considered options

- **Axis separation (a prior version of this ADR, now reversed).** An S-cell
  contributes *both* digits as two `add_all_different` members — the same as
  digits-distinct — and values-distinct differs from digits-distinct *only* for
  a modifier cell. Rejected: it contradicts issue #236's acceptance criteria,
  which always read an S-cell as one combined value ("a `23`-valued S-cell
  coexists with a plain 2 or 3"), and it splits "value" into two mechanisms —
  a combined value for doublers, a two-member expansion for S-cells — where the
  seam already gives one combined value for both. The domain owner's model is the
  single combined value, and the value methods already express it.

- **Offset the two encodings apart** so a doubler's value and an S-cell's
  combined value never share an integer key. Rejected: two cells with the same
  value are supposed to collide; offsetting them apart defeats the mode. `18` is
  `18`.

- **Fix the `combine` rule at `concat`.** Rejected: two digits genuinely combine
  sometimes by a sum and sometimes by a concatenation, so it must be a declared
  property, and the Schrödinger layer is its owner.

## Consequences

- A cell's value lives in one place — the channel the owning layer reifies — and
  every consumer reads it through `value_expr`, blind to which layer built it.
  The values-distinct cage is the seam's consumer; `group-sum`, the killer
  sum's later home, folds a modifier's `modifier_value` but declines the rest
  of the seam by its own S-blind decision (decision 6). Making the Schrödinger
  layer register `s_value` the way the doubler registers `modifier_value` is
  what lets the cage drop all S-cell and modifier special-casing.
- The Schrödinger layer registers `s_value` in phase 1 (`register`), so the
  cage's phase-2 read sees it whatever the stack order. This is the same ground
  issue #255 is working (whether the seam subsumes discovered modifiers). This
  decision names the cage's needs; the seam's shape is settled there.
- The doubled-S-cell guard is a deliberate ceiling, recorded so a future reader
  lifts it through the coexistence path rather than reading the raise as an
  accident. It still guards the values-distinct cage; the killer sum no longer
  reaches it (decision 6).
