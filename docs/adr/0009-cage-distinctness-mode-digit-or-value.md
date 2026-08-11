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

2. **A cell's value is what the value methods return — the cage does not define
   its own.** The value seam (ADR-0004) is the single definition of a cell's
   value: a plain cell's value is its digit, a doubler's is its doubled amount
   (the `modifier_value` a modifier layer reifies), an S-cell's is its two
   digits folded. A values-distinct cage reads each cell's value through that
   seam and puts it in one `add_all_different`. It does not hand-roll a fold of
   its own — a bespoke `10·d0 + d1` in the cage would be a second, divergent
   definition of the same thing.

3. **Same value collides — always, with no exception.** Two cells clash exactly
   when their values are the same number. A doubler worth 18 and an S-cell that
   folds to 18 collide, because a value is a number and 18 equals 18. There is no
   offset, no separate band, no rule that a "doubled 18" and a "folded 18" are
   different — they are the same value, so they repeat. An earlier draft proposed
   offsetting the two encodings apart; that was wrong, and it would have let two
   equal values sit in one cage.

4. **How an S-cell folds is a puzzle-wide property, owned by the Schrödinger
   layer.** Two digits become one value by a **fold** — `sum` (2 + 3 = 5) or
   `concat` (2, 3 → 23). Which one is a property of the whole puzzle, not of the
   cage or the cell, and the Schrödinger layer owns it: it is the layer that
   widens a cell to two digits, so it names how those two digits read as one
   value. Every values-distinct read of an S-cell in that puzzle uses the same
   fold.

5. **A doubled S-cell stays deferred.** A cell that is both a doubler and an
   S-cell has no defined value yet — no link can encode both marks (they share
   the red color bit, ADR-0008) and nothing models the combination. The cage
   asserts a modifier cell is width-1, so the unconstructable state fails loudly
   instead of silently mis-valuing the cell. The combination arrives with the
   rest of doubler-plus-S-cell coexistence, not here.

6. **The killer sum is unaffected by the mode.** A cage's sum already folds
   modifiers unconditionally (ADR-0008): a doubler counts as `2·d0` whatever the
   `distinct-over` mode, because the doubler exists to change the total. Only the
   no-repeats half answers to `distinct-over`.

7. **`distinct-over` is an internal param with no decoder yet.** No SudokuMaker
   link we have carries a distinctness mode. The cage constraint accepts the key
   (its params are an open dict) and defaults to `digit`; the wire decoder stays
   untouched until a real values-distinct link shows which bit carries the mode.

## Considered options

- **Axis separation (a prior version of this ADR, now reversed).** An S-cell
  contributes *both* digits as two `add_all_different` members — the same as
  digits-distinct — and values-distinct differs from digits-distinct *only* for
  a modifier cell. Rejected: it contradicts issue #236's acceptance criteria,
  which always read an S-cell as one folded value ("a `23`-valued S-cell
  coexists with a plain 2 or 3"), and it splits "value" into two mechanisms —
  a folded value for doublers, a two-member expansion for S-cells — where the
  seam already gives one folded value for both. The domain owner's model is the
  single folded value, and the value methods already express it.

- **Offset the two encodings apart** so a doubler's value and an S-cell's folded
  value never share an integer key. Rejected: two cells with the same value are
  supposed to collide; offsetting them apart defeats the mode. `18` is `18`.

- **Fix the fold at `concat`.** Rejected: the fold is genuinely sometimes a sum
  and sometimes a concatenation, so it must be a declared property, and the
  Schrödinger layer is its owner.

## Consequences

- The value seam becomes the one place a cell's value is defined, for the killer
  sum and the values-distinct rule alike. A values-distinct cage that reads the
  seam rather than its own fold is the same read a modifier-aware distinctness
  needs, so folding the doubler in falls out of the seam, not a special case in
  the cage.
- Sourcing the fold from the Schrödinger layer, and reading a doubler's value at
  model-build time, both touch the value seam — the same ground issue #255 is
  working (whether the seam subsumes discovered modifiers). This decision names
  the cage's needs; the seam's shape is settled there.
- The width-1 assertion is a deliberate ceiling on doubled S-cells, recorded so a
  future reader lifts it through the coexistence path rather than reading the
  guard as an accident.
