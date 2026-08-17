# ADR-0017: somedoku is a row-*n*/col-*n* distinct-count rule, declared by a two-carrier global flag

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decides:** what the somedoku rule is, how a SudokuMaker link declares it,
  and that it is a real, link-reachable, found/broke-proven variant — not the
  permanently code-tested-only case ADR-0007 declared it.

## Context

`line-count-distinct` existed as a layer (`layers/line_count.py`) with two
problems. First, the rule it stated was wrong: it constrained rows only —
row *n* holds *n* distinct digits — when somedoku's actual rule constrains
columns the same way. Second, it had no decode path, so no SudokuMaker link
could turn it on; ADR-0007 named this *permanent*, since a constraint with no
wire type and no flag can never be expressed by a link.

Spec #436 (grilling #405) settled both: the corrected rule, and a decode path
through the named-component registry (spec #431).

## Decision

1. **The rule constrains both axes.** For each *n* in `1..size`, row *n* and
   column *n* each hold exactly *n* distinct digits, repeats allowed
   (`layers/line_count.py`'s row pass plus its column pass, #512). Somedoku is
   a standalone puzzle: no regions, no boxes, no classic row/column
   uniqueness — incompatible with a distinct-count target below the board
   size, since row/col 1 collapse to a single repeated digit and only
   row/col *size* recovers ordinary uniqueness, for that one line alone.

2. **Somedoku is a `global-flag` named component** (`naming.py`'s third
   registry shape, alongside `cage-selector`/`cell-marker`): a name needing no
   payload at all. The `Somedoku` name (case-insensitive, trimmed) is
   registered against it with role `"somedoku"`.

3. **Two carriers, one recognizer.** Because the shape needs no payload,
   carrier-fitness admits `Somedoku` on both a `type 1000` custom
   constraint's `definition.name` and a `type 2001` cosmetic cage's top-level
   `name` — the one shared `naming.named_component` lookup
   (`sudokumaker/global_flags.py`'s `has_somedoku_component`). gridfind never
   interprets a `type 1000` block's programmed logic — it is opaque — so name
   is the whole recognition signal on either carrier. Presence alone is the
   rule; a component's cells and value are read on neither carrier.

4. **Decode emits `line-count-distinct` in place of the classic triplet.**
   `link_to_puzzle` swaps `rows-distinct`/`cols-distinct`/`regions-distinct` for
   a single `line-count-distinct` constraint when the flag is set, and skips
   `type 1`'s regions/box rule the same way — a somedoku grid carries no
   boxes. A disabled `Somedoku` block, on either carrier, decodes to nothing
   and the classic triplet stands.

5. **Somedoku owes (and now carries) a found/broke link pair**, joining
   ADR-0007's coverage-floor policy as an explicit link-reachable variant
   (`links_test.py`'s `_EXPLICIT_VARIANTS`), since it arrives by a named
   component rather than a one-to-one `DECODER_REGISTRY` wire type.
   `found-somedoku-9x9` mirrors the setter's real `type 1000` link — zero
   givens, which the rule alone leaves solvable. `broke-somedoku-9x9` adds
   two givens in column 1, whose target of 1 distinct digit two different
   digits already exceed.

## Considered options

- **Keep `line-count-distinct` code-tested only.** Rejected: ADR-0007 named
  this permanent specifically because no wire type or flag existed for it —
  once the named-component registry supplies one, the premise no longer
  holds, and the rest of ADR-0007's policy (every link-reachable variant owes
  a found/broke pair) applies unchanged.
- **Interpret the `type 1000` block's programmed logic.** Rejected: it is
  opaque SudokuMaker script, not a data payload gridfind can read; name-only
  recognition is the only signal available, and it is sufficient since a
  setter names the constraint for the rule they intend.
- **Admit the `Somedoku` name on only one carrier.** Rejected: nothing in the
  shape distinguishes the two carriers — a global flag needs no payload on
  either — and setters use both (a real programmed constraint, or a
  lightweight cosmetic-cage flag) to declare the same intent.

## Consequences

- ADR-0007's "`line-count-distinct` is code-tested only, permanently"
  consequence is retracted.
- The registry's warn-drop policy (`registry.warn_on_dropped_constraints`)
  treats a recognized global-flag component as decoded, not dropped,
  regardless of its own live/inert payload — it is never a misplaced
  declaration.
- `witness_validator.validate_witness`'s row/column permutation checks are
  conditional on `rows-distinct`/`cols-distinct` actually being among the
  puzzle's constraints, mirroring its existing `regions-distinct` handling —
  somedoku is the first link-reachable variant without classic row/column
  uniqueness.
- Graduates somedoku from map #397's charter *partial* to *working*: it now
  decodes from a real link, and its found/broke pair proves it end to end
  through `cli.main`.

## When to revisit

Revisit if a second global-flag component needs a payload after all — the
shape declares "nothing," and a component that turns out to need cells or a
value belongs under `cage-selector`/`cell-marker` instead, not a payload
bolted onto `global-flag`.
