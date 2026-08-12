# ADR-0008: doublers are declared color-marked cells; cosmetic cages carry real killer sums

- **Status:** Accepted
- **Date:** 2026-08-11
- **Decides:** how a SudokuMaker doubler link decodes — where the doubler mark
  lives, what a color-marked cell means, and why a "cosmetic" cage must be read
  as a killer cage (parent [#232](https://github.com/caneff/gridfind/issues/232),
  decode [#265](https://github.com/caneff/gridfind/issues/265), solving [#237]).

## Context

A **doubler** is a cell whose placed digit counts as `2·d0` in constraint
arithmetic. Put a doubler inside a killer cage and the cage's true sum can run
past what standard digits reach — over 45 in a 9×9 — so SudokuMaker's
killer-cage tool refuses to store that sum at all.

Setters work around it two ways, and a real link confirms both. Decoding
author "ChinStrap"'s 4×4 (`type: sudoku`, 2×2 boxes): the doubler cell R1C2
carries `{"colors": 2}` — red, the same bit an S-cell uses — and the cage lives
in a **type-2001** block as
`{"cages": [{"value": "11", "cells": [R1C1, R1C2, R1C3]}]}`, while the real
**type-301** killer block sits empty and `solverIgnored`. The doubler sits
inside the cage, so the sum is `R1C1 + 2·R1C2 + R1C3 = 11`, out of range for a
plain cage — pushed into a cosmetic cage with the sum kept as a display string.

> **Corrected (2026-08-12, #317):** an earlier draft recorded the cosmetic
> block's cells and value as flat (`{"value": "11", "cells": [...]}`).
> SudokuMaker nests them under `cages`, the same wire shape as a type-301
> killer block — a block may carry several cages. The decoder now reads that
> shape; the flat form it read before does not round-trip in SudokuMaker (the
> app registers no cells for it), so the `found-doubler` / `broke-doubler`
> fixtures were regenerated from real exports. The "cosmetic cage is a killer
> cage" decision below is unchanged — only its wire shape was wrong.

Today gridfind ignores the color bit unless `schrodinger=True` and drops
type-2001 as cosmetic, so it computes the verdict with **neither** the doubler
nor the cage — unsound for this puzzle.

## Decision

1. **A doubler is a declared position.** The color mark is part of the puzzle
   definition, so decode pins `is_modifier` for that cell. It is not a
   discovered position exported in a solved state — the link is an unsolved
   puzzle carrying the mark, and every ISS special-cell feature is likewise
   setter-declared.
2. **Doubler decode is flag-gated** — `decode_link(doubler=True)`, reading the
   red bit by default, mirroring `schrodinger=True`. A bare color bit is
   ambiguous, so the variant is declared, never sniffed.
3. **Cosmetic (type-2001) cages are honored as killer cages.** A numeric string
   `value` becomes the killer sum; ~~a non-numeric or empty label stays inert and
   drops as before~~. This is the only channel an out-of-range cage sum reaches
   gridfind through, since SudokuMaker cannot store it as a real killer cage.

   > **Superseded (2026-08-12, #298):** the struck clause no longer holds. A
   > non-numeric or empty label no longer drops — every non-disabled cosmetic
   > cage is a killer cage, emitting a no-repeats `cage` with a `group-sum` only
   > when a numeric `value` graduates, exactly as a sumless `type-301` cage
   > emits `cage` alone. The numeric-sum channel above is unchanged, so the
   > doubler puzzle (label `"11"`) still graduates as this ADR describes.
4. **The killer sum folds modifiers.** A doubled cell contributes `2·d0` via
   the `modifier_value` structure (#237's pattern), not its raw content. The
   killer cage later recomposed as `cage` (uniqueness) plus `group-sum` (the
   total), each a separate constraint over the same cells (spec #240, issue
   #243); the fold this decision names is `group-sum`'s today, the cage
   stating no sum of its own.

## Considered options

- **Discovered doubler position** — the solver deduces which cell is the
  doubler, the mark being a solution export. Rejected: the real link is an
  unsolved puzzle whose definition carries the mark, and ISS has no
  discover-then-export precedent.
- **Refuse links carrying both S-cells and doublers.** Both ride the red bit, so
  one grid cannot encode both. Rejected as the permanent ceiling in favor of the
  coexistence path: **the CLI names which color carries which meaning.** Not
  built now — no combined link exists to model (YAGNI) — but recorded so
  coexistence is never later "solved" by refusing both or a worse hack.
- **Keep dropping cosmetic cages as decoration** (today's behavior). Rejected:
  for a doubler puzzle the cosmetic cage is the *only* carrier of the real
  killer sum, so dropping it computes an unsound verdict.

## Consequences

- Honoring a type-2001 "cosmetic" cage as a real constraint is surprising
  without this context — this ADR is the why.
- The work splits into three tickets under #232 — cosmetic-cage graduation, the
  doubler decode (#265), and the modifier-aware cage sum — and the
  `found-doubler-*.txt` / `broke-doubler-*.txt` E2E fixture blocks on all three,
  since one real link exercises every one.
