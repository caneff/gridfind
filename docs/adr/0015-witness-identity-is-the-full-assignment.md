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

The implementation reaches this rule in steps. T2 dedups on the digit `d0` per
cell — the full identity for the plain-digit grids it enumerates, since those
carry no S-cell or modifier content. T3 widens the identity tuple to the full
assignment (S-cell pair and modifier terms included), at which point the code
matches this ADR term for term. The rule stated here is the target the identity
tuple grows into, not a description of the d0-only tuple T2 ships.
