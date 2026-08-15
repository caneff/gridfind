# ADR-0016: a shared `Modifier` base; the constant modifier carries `k` in its cage name

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decides:** how a second modifier type is added — the base every modifier
  type shares, and how a **constant modifier** (a **nullifier** is its `k = 0`
  case) declares its constant through a SudokuMaker link.

## Context

Until now the **doubler** is the only modifier. `ModifierPlacement` states the
placement rule every discovered-modifier puzzle shares — one modifier per row,
column, and box, and a distinct-digit transversal — but it is *placement only*
by explicit design. The **value-fold** plumbing (register `modifier_value`, wire
`== underlying` when the cell is free and `== 2·underlying` when the solver
discovers it a modifier, register `modifier_type`) lives entirely inside
`Doubler`; `Doubler` composes `ModifierPlacement` and hand-rolls the rest. The
`modifier.py` docstring *promises* "a future modifier type supplies only its own
value fold," but the seam that would make that true was never built.

Adding a **constant modifier** — every modified cell worth a fixed `k`,
independent of its digit, the **nullifier** being `k = 0` — needs that seam. It
also needs a channel for `k`, which a doubler never needed (`2·` is fixed).

## Decision

1. **A shared `Modifier` base owns the value plumbing.** It composes
   `ModifierPlacement`, registers `modifier_value` and `modifier_type`, and
   wires both branches of each cell's value (free → the underlying value,
   discovered → the modified value). Each concrete supplies only two things: the
   **value a modified cell takes**, as an expression over the cell's underlying
   value, and that value's **bounds**, so the base can size the `modifier_value`
   domain to cover both branches. `Doubler` returns `2·underlying`;
   `ConstantModifier` returns its constant `k`. `ModifierPlacement` stays
   placement-only beneath the base, reused unchanged.

2. **`k` is the `constant` constraint's own parameter.** A modifier layer runs
   with no marker cages — positions are discovered by the transversal — so the
   constant cannot live on a cage. It lives on the constraint
   (`{type: constant, value: k}`), the one home. `build_stack` reads the param
   and builds a fresh `ConstantModifier(value=k)`, exactly as a `regions-distinct`
   constraint carrying `params["regions"]` builds a fresh partition-closed layer;
   a bare `constant` with no value falls to the registry default `k = 0`.

3. **A link declares `k` in the marker-cage name, not a per-cage `value`
   field.** A `Constant <N>` cosmetic cage marks its cells constant modifiers and
   carries `k = N` read from the name itself; `Nullifier` is the spelling for
   `Constant 0`. A marker cage marks *positions*, and `k` is a puzzle-wide fact —
   there is no global `value` channel on cages, only a per-cage `value` field
   that two cages could disagree on. So a `value` field on any marker cage is
   refused, and the name is the only channel a puzzle-wide constant rides. This
   departs knowingly from the `Sum`/`Killer` precedent, where the cage's `value`
   field carries the number (ADR-0008): a killer sum is genuinely per-cage, a
   modifier's `k` is not.

4. **One modifier type per puzzle.** A grid carries a doubler *or* a constant
   modifier, never both, and a constant modifier at one `k`. Coexistence — two
   kinds, or one kind at two values of `k`, over one grid — needs a per-cell type
   discriminator and per-type placement, a materially larger change with no link
   to serve yet. The base is shaped so a second modifier layer in the stack is
   not *foreclosed*; it is simply not built. A link mixing kinds, or `Constant`
   cages that disagree on `k`, is refused rather than silently merged.

## Considered options

- **Carry `k` in the cage's `value` field**, mirroring the killer sum. Rejected:
  `k` is puzzle-wide, cages have no global value channel, and per-cage values
  invite disagreement. The name is the puzzle's per-type channel.
- **Copy `Doubler`'s plumbing into a second layer.** Rejected: two homes for the
  same value wiring drift apart — the repo's dominant refactor is collapsing
  exactly this (CODING_STANDARDS, "one home per behavior").
- **Build coexistence now.** Rejected as premature: no link carries two modifier
  kinds, and the placement/value machinery it needs is large. Deferred, not
  foreclosed.

## Consequences

- The name → shape registry grows a **parameterized-name** path: `Constant <N>`
  is no longer a static key, so `naming` parses the trailing integer, and the
  readers that treat names as a finite set adapt — `cosmetic_cage_kind` returns
  kind `constant` after stripping `N`, the setter guide renders the label
  `Constant <N>` rather than enumerating, marker colorizing groups by kind
  unchanged. A bare `Constant` with no parseable integer is unrecognized and
  warn-dropped, like any unknown cage name; `Nullifier` / `Constant 0` are the
  `k = 0` spellings.
- `k` may be any integer, negatives included — the value seam is arithmetic and
  a value is just a number (ADR-0009, decision 3). Only a `value` string that
  will not parse to an integer is refused, as an out-of-domain given is.
- The doubler docstring's promised seam becomes real: `Doubler` shrinks to its
  one value expression, and the next modifier type after `constant` is the same
  small addition.
