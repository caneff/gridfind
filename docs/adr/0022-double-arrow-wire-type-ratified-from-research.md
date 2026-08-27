# ADR-0022: wire type 409 is the double-arrow line, ratified from research

- **Status:** Accepted
- **Date:** 2026-08-26
- **Decides:** that SudokuMaker wire type 409 decodes to the double-arrow
  line relation, and that this decode fact ships ratified from #670's
  research plus the synthesized corpus, without a captured real type-409
  link (spec [#672](https://github.com/caneff/gridfind/issues/672) /
  [#678](https://github.com/caneff/gridfind/issues/678), verify flag
  [#670](https://github.com/caneff/gridfind/issues/670)).

## Context

A **double-arrow line** reads broke when its interior digits do not sum to
the sum of its two bulb ends. Issue #670 ratified this relation — interior
sum equals endpoint sum, value seam, positional endpoints, reversal-invariant
— against the eev.ee variant catalog (a high-authority source for the
*genre*), and flagged that the genre confirmation is not the same as a wire
confirmation: no SudokuMaker source maps type 409 to double-arrow, and the
#668 capture that first named the type decoded only its bare `lines` wire
shape, not which relation it carries.

Issue #678 carried this forward as a build-time verify: confirm 409-is-
double-arrow, and that a between-line (403) and a double-arrow (409) are
told apart by wire type rather than glyph, against a captured real link,
before the emitter ships. No real type-409 link was captured. The found/broke
corpus is synthesized in code (`scripts/synthesize_double_arrow_links.py`),
not exported from a live SudokuMaker double-arrow puzzle.

Unlike lockout's threshold (ADR-0021), this fact *is* in principle
wire-observable — a captured link could show which relation a real type-409
block encodes. But the type-vs-glyph half of the flag is already structurally
guaranteed regardless: the decoder dispatches every wire block purely by its
`type` integer (`DECODER_REGISTRY`, `enabled_blocks`) and never reads a glyph,
style, or drawing hint anywhere in the line-clue family. A captured link would
only confirm the same decode-shape fact #678's other acceptance criteria
already exercise (a 403 block and a 409 block decoding to different
relations) — it carries no further threshold or shape the corpus doesn't
already pin.

## Decision

**Ratify wire type 409 as the double-arrow relation on the strength of #670's
research (the eev.ee variant catalog) and the synthesized found/broke corpus.
A captured real link is not a ship gate for this fact.**

1. **One home for the mapping.** `wire_types.DOUBLE_ARROW_TYPE = 409` is the
   only place the type number is named; `sudokumaker/line.py`'s
   `double_arrow_constraints` and `registry.DECODER_REGISTRY`'s `409` row
   both read it from there.

2. **The corpus pins the relation.** The synthesized found/broke pair gives
   both bulbs and drives the interior cell through the exact sum equality, so
   a wrong relation (or a swapped 403/409 mapping) turns the on-demand e2e
   suite red — the same guard every value-mode relation ships behind.

3. **Same posture as lockout (ADR-0021) and grouped-line.** Each shipped a
   semantic or wire fact from spec/research and a synthesized corpus rather
   than blocking on a real capture, recording the ratification here so a
   later real link is a confirming (or correcting) swap, not a rebuild.

## Consequences

- Issue #670's build-time verify is discharged by this ratification, recorded
  here. The double-arrow wire-type comment and `_double_arrow` docstring cite
  **ADR-0022**, not the closed issue number.
- If a real SudokuMaker type-409 link later shows a different relation, the
  fix is a one-function change in `layers.line._double_arrow` (and, if the
  type number itself is wrong, a one-constant change in `wire_types.py`) plus
  a corpus regen — no decode-shape or dispatch change.
