# ADR-0015: two witnesses are distinct iff their full per-cell assignment differs

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decides:** what makes two completions of a puzzle *different* when
  `enumerate_witnesses` counts distinct witnesses (spec
  [#389](https://github.com/caneff/gridfind/issues/389), decision #381).

## Context

`enumerate_witnesses` answers "show me up to N different ways to fill this
puzzle." That question needs one thing pinned down: when are two filled grids
the *same* answer and when are they two? Without a rule, an enumeration either
double-counts grids a caller would call identical, or collapses grids a caller
would call different — and either way the count it reports is meaningless.

CP-SAT's `enumerate_all_solutions` enumerates distinct *variable assignments*.
Left alone it can also fold solutions together by symmetry, which would hide
completions a puzzle solver counts as real. So the identity rule and the solver
settings that honor it are one decision, not two.

ISS is no guide here: it stops at the first solution and makes no uniqueness or
count claim (CONTEXT.md, **found**). The authority is gridfind's own witness
model and #381's acceptance.

## Decision

1. **Two witnesses are distinct iff their full per-cell assignment differs.**
   The identity of a witness is its whole grid — every cell's placed content,
   read literally. Two witnesses are the same witness only when every cell
   holds the same content in both; they are two the moment any one cell
   differs. A cell's content is its digit for a plain cell, its ordered digit
   pair for a Schrödinger S-cell, and it carries any modifier the solve placed
   — the full assignment, nothing dropped.

2. **No symmetry reasoning.** The rule is taken literally: two grids that are
   the same up to a relabeling of digits, a reflection, or any other symmetry
   are still two distinct witnesses if any cell's content differs. gridfind
   never declares two literally-different grids "the same puzzle." Phase 2 runs
   `enumerate_all_solutions` with `symmetry_level=0` so the solver does not fold
   symmetric solutions away beneath this rule.

## Consequences

The count `enumerate_witnesses` reports is the literal number of distinct
filled grids, up to the caller's `limit`. A caller who wants "unique solution"
asks for two and reads whether the second exists.

Phase 2 dedups on the full witness content: each cell's digit sequence (a
widened S-cell's ordered pair, else its lone `d0`) and every discovered
modifier. For a plain-digit grid this is the digit per cell and nothing more; a
Schrödinger or modifier stack carries the S-cell pair and doubler placement
along, so the key matches this rule term for term.

The wider key counts completions a first-digit-only key would merge. Two
completions can share every first digit yet be distinct: a 2×2 over `{0,1,2}`
with one S-cell per line has six completions but only four first-digit grids —
two grids each carry a pair that places the S-cell on the other cell of the
line, same `d0`, different two-digit content. A fully-given 4×4 sudoku grid
fixes every digit, and its doubler — one per row, column, and box, all digits
different — still admits four placements, each a distinct completion on its
placement alone. A first-digit-only key would count four and one; the
full-content key counts six and four.

Phase 2 dedups in the callback because CP-SAT enumerates distinct *variable*
assignments over the whole model, auxiliary variables included, so several
solver solutions can carry one witness; keying on the witness content folds
those together (spec #389, decision #383).
