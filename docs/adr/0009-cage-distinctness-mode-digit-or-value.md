# ADR-0009: a cage's no-repeats mode is digit or value; the killer sum always folds

- **Status:** Accepted
- **Date:** 2026-08-11
- **Decides:** what "distinct" means in a cage that holds a **modifier** — over
  the placed digits or over the folded values — and why the choice sits only on
  the no-repeats half, never the killer sum (parent
  [#232](https://github.com/caneff/gridfind/issues/232),
  ticket [#236](https://github.com/caneff/gridfind/issues/236)).

## Context

A cage forbids its cells from repeating. Put a **doubler** in the cage and
"repeating" splits in two: a doubler showing 3 has value 6, so does it clash
with a plain cell showing 6 (same value) or a plain cell showing 3 (same
digit)? Both readings are real killer variants, and gridfind has to pick which
a given cage means.

ISS is no guide here — it has no doublers, no modifiers, and no Schrödinger
cells, so its cage is a fixed digit-distinct `AllDifferent` with nothing to
toggle. gridfind carries all three, so it has a distinction ISS cannot express
and must resolve on model coherence alone.

The pieces already in place: a doubler's folded value is the reified
`modifier_value` structure (`d0` normally, `2·d0` when the cell is the
discovered modifier), which `pair-sum` already reads; the cage's no-repeats
half reads raw content slots (digit-distinct); and the cage's killer sum
already folds modifiers unconditionally (ADR-0008).

## Decision

1. **A cage carries a `distinct-over` mode: `digit` (default) or `value`.** A
   **digits-distinct** cage forbids a repeated digit — today's rule, unchanged.
   A **values-distinct** cage forbids a repeated folded value. The default
   preserves the classic killer convention, so every existing cage keeps its
   verdict.

2. **Values-distinct folds modifiers only; an S-cell stays two digits.** A cell
   contributes its folded slots to one `add_all_different`: a doubler its single
   `modifier_value` (`2·d0`), a plain cell its digit, an S-cell both of its
   digits unchanged. An S-cell is a superposition of two digits, not a
   value-modified cell — every other distinctness rule already treats its two
   digits as two house members, and values-distinct keeps that. On a plain
   puzzle no cell has a `modifier_value`, so the set is every raw slot and
   values-distinct *is* digits-distinct — the regression holds by construction,
   not by a parallel code path.

3. **The killer sum always folds; only the no-repeats half toggles.** A cage's
   sum counts a doubler as `2·d0` whatever the `distinct-over` mode — the
   doubler exists to change the total. The two halves answer to different
   conventions on purpose: a killer sum is arithmetic, so it is always
   value-based; killer distinctness is over placed symbols, so it defaults to
   digit and opts into value.

4. **`distinct-over` is an internal param with no decoder yet.** No SudokuMaker
   link we have carries a distinctness mode. The cage constraint accepts the key
   (its params are an open dict) and defaults to `digit`; the wire decoder stays
   untouched until a real values-distinct link shows which bit carries the mode.

5. **A doubled S-cell is deferred and guarded.** A cell that is both a doubler
   and an S-cell would fold to `[2·d0, 2·d1]`, but no link can encode both marks
   (they share the red color bit — ADR-0008) and nothing models the combination.
   Values-distinct asserts a modifier cell is width-1, so the unconstructable
   state fails loudly instead of silently dropping the cell's second digit from
   the distinctness set. The full two-slot fold arrives with the rest of
   doubler-plus-S-cell coexistence, not here.

## Considered options

- **One compound value per cell** — a plain cell is `d0`, a doubler `2·d0`, an
  S-cell the positional `10·d0 + d1` (the "23" an S-cell reads as). Rejected: it
  invents a compound-value notion no other rule uses, and since `23` can never
  equal a single digit, an S-cell in such a cage collides with nothing — the
  distinctness rule stops constraining it at all. It matched one acceptance-
  criteria example and nothing deeper.
- **Fold the distinctness and the sum together** — one mode governs both halves.
  Rejected: it forces a killer sum to stop counting a doubler double whenever the
  setter wants digit-distinctness, which breaks the doubler's whole purpose.
- **Build the doubled-S-cell fold now.** Rejected as YAGNI with a sharp edge: the
  state cannot be decoded or constructed today, so the fold would be untested
  code shaping a verdict; the width-1 assertion is the cheap correct stand-in.

## Consequences

- A cosmetic cage honored as a killer cage (ADR-0008) and a values-distinct cage
  are the two ways a modifier reaches a cage's arithmetic; together they let one
  doubler puzzle solve soundly.
- The `distinct-over` param is live in the model but dead on the wire until a
  link needs it — a reader of the decoder will find no path that sets it, by
  design.
- The width-1 assertion is a deliberate ceiling on doubled S-cells, recorded so a
  future reader lifts it through the coexistence path rather than reading the
  guard as an accident.
