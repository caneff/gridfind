# ADR-0011: an absent board size is the classic 9×9, never inferred from cells

- **Status:** Accepted
- **Date:** 2026-08-12
- **Decides:** how link verification reads a board's size — what an absent
  `size`/`width` header means, and why a sizeless non-81-cell link is rejected
  rather than resized to fit its cells.

## Context

A SudokuMaker link states its board with `size` (square) or `width`/`height`
(non-square). The field-by-field study in
[`sudoku-link-formats.md` §4b](../research/sudoku-link-formats.md) settled the
rule against three real links: **SudokuMaker omits a header only when it equals
the classic default** — a non-9 *square* carries `size` (the real 6×6 sample
has `size: 6`), a non-square carries `width`; only the classic 9×9 omits both.

gridfind's decoder did the opposite for the absent case: it inferred
`size = isqrt(len(cells))`. That silently disagrees with the app. A 16-cell
link with no `size` decoded as a 4×4 in gridfind, while SudokuMaker — which
defaults an absent size to 9×9 — opens it as a (malformed) 9×9. gridfind was
verifying a board the app never shows, and the link-eval view emitted links
that reopened at the wrong dimensions.

## Decision

Link verification derives the board from the **stated** size, defaulting an
absent `size`/`width` to the classic **9×9** — SudokuMaker's own fallback — and
never inferring the size from the cell count. The existing
`rows * cols == len(cells)` cross-check then rejects a sizeless non-81-cell
link with `ValueError`: a real 4×4 or 6×6 carries its `size`, so one that omits
it is malformed, not a small board to be guessed.

Solution-link emission (`emit_solution_link`) always writes an explicit `size`
from the known board, so a re-emitted witness link opens at the right
dimensions even when the source omitted the header.

## Consequences

- A classic 9×9 link (81 cells, no header) still decodes as 9×9 — the default
  is exactly its inferred value, so nothing changes for the common case.
- Three corpus links that omitted `size` on a sub-9×9 board were malformed
  captures; they now carry their real `size` (4 or 6). Adding it is
  decode-invariant — gridfind already built that board — but makes them open
  correctly in the app.
- A non-square link is unaffected: it carries `width`, read before this
  default applies.
