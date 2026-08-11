# ADR-0010: a doubled Schrödinger cell is worth twice its combined value; the default combine is sum

- **Status:** Accepted
- **Date:** 2026-08-11
- **Decides:** what value a cell that is *both* a doubler and a Schrödinger cell
  carries, where the doubling happens, and what the puzzle-wide `combine` rule
  defaults to. **Supersedes [ADR-0009](0009-cage-distinctness-mode-digit-or-value.md)
  decision 5**, which deferred this cell (parent
  [#232](https://github.com/caneff/gridfind/issues/232), ticket
  [#239](https://github.com/caneff/gridfind/issues/239)).

## Context

ADR-0009 decision 5 recorded a doubled S-cell as having no defined value yet —
`value_expr` raised rather than pick between the two value channels the cell sat
in. That deferral was deliberate: nothing modeled the combination, and no link
could mark a cell both ways.

The rule turns out to need nothing special. A modifier modifies a cell's
*value*; an S-cell's value is its `s_value`; so a doubled S-cell is worth
`2·s_value`. The composition falls out of "a modifier maps the value," with no
new mechanism. What the deferral was really waiting on is the *encoding* — a way
to mark one cell as both — and the model already allows that even though no link
does.

ISS is no guide here: it has no doublers and no Schrödinger cells (ADR-0009). The
authority is gridfind's own value-channel model (ADR-0008, ADR-0009) and #239's
acceptance criteria.

## Decision

1. **A doubled S-cell is worth `2·s_value`.** The doubler maps the cell's value,
   and the Schrödinger layer already reified that value into `s_value`, so the
   doubled value is twice it. This supersedes ADR-0009 decision 5's deferral:
   the cell has a defined value, and `value_expr` no longer raises for it.

2. **The doubler folds the value beneath it; the seam stays dumb.** The doubler
   stops reading the raw digit `d0` and instead doubles the value underneath it —
   `s_value` when a Schrödinger layer is present, else the digit — writing the
   result into its `modifier_value` channel (tolerating `s_value`'s absence like
   every other late-bound structure). Because the doubler already registers
   `modifier_value` for every cell, that channel now subsumes `s_value`, and
   `value_expr` collapses to a plain precedence: `modifier_value → s_value →
   digit`, each layer's value already folding the one beneath it. The
   both-channels raise is deleted, not special-cased around. The `2·` coefficient
   stays in the doubler, never in `value_expr` — a reader hand-rolling `2·s_value`
   is the exact anti-pattern ADR-0009 decision 2 forbids.

3. **The guard lifts everywhere `value_expr` is read.** Once the seam returns
   `2·s_value` instead of raising, both readers — the values-distinct cage and
   the killer sum (`group-sum`) — value a doubled S-cell through the one rule. A
   partial lift (sum composes, cage still raises) would put the special case back
   inside `value_expr`, which is what this decision removes.

4. **This is settled ahead of the encoding.** The model already permits a cell
   to carry both marks — `is_modifier` and `is_s` are independent booleans, so
   nothing stops both being true. Only the *link* cannot say "both": ADR-0008
   puts the doubler mark and the S-mark on the same red color bit. So the rule is
   built and tested at the engine level by hand-marking a cell both ways, with no
   decoder. Reaching a doubled S-cell from a real SudokuMaker link is separate,
   later work — the coexistence encoding — the way ADR-0009 decision 7 keeps
   `distinct-over` an internal param with no wire decoder yet.

5. **The default `combine` rule is `sum`, not `concat`.** A Schrödinger cell
   holds two digits, and the classic variant adds them, so `sum` (2, 3 → 5) is
   the right default; `concat` (2, 3 → 23) stays a choosable rule for a puzzle
   that declares it. Under `sum` a doubled S-cell is `2·(d0 + d1) = 2·d0 + 2·d1`,
   so #239's `[2·d0, 2·d1]` picture is literally the value.

## Considered options

- **Compose in the seam** — let `value_expr` return `2·s_value` itself when a
  cell sits in both channels. Rejected: it hard-codes the doubler's `2·`
  coefficient into a reader, a second home for a value the doubler owns — the
  anti-pattern ADR-0009 decision 2 names. Folding in the doubler keeps one owner.
- **Carry the value as a literal pair `[2·d0, 2·d1]`** and reduce it at each
  consumer. Rejected: `value_expr` returns one scalar, and every reader — the
  values-distinct cage's `add_all_different`, the killer sum — adds one number
  per cell. A pair forces a second shape through a seam built for one.
- **Keep `concat` as the default.** Rejected: a Schrödinger cell's two digits
  add in the standard variant, so `sum` is the truer default. `concat` remains
  available for a puzzle that declares it.

## Consequences

- `value_expr` loses its both-channels branch entirely — the precedence
  `modifier_value → s_value → digit` values every cell, including a doubled
  S-cell, because each channel already folds the one beneath it.
- Flipping the `combine` default re-values *every* plain S-cell, not just doubled
  ones: a lone S-cell holding 2 and 3 goes from 23 to 5. That change is its own
  ticket, landed before #239, so #239's diff carries one decision, not two.
- ADR-0009 decision 6's prose was already stale before this ADR: it claimed
  `group-sum` is "S-blind" and "raises not-Schrödinger-ready" over a named
  S-cell, but issue #235 retired that refusal and `group_sum.py` reads `s_value`
  through `value_expr` today. That decision is corrected in the same pass.
- The remaining gate is the coexistence encoding — a link bit (or engine mark)
  that says "this cell is both." Until it lands, a doubled S-cell is reachable
  only from a hand-built engine, not a real link.
