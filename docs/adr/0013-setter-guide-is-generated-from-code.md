# ADR-0013: the accepted-link setter guide is generated from code

- **Status:** Accepted
- **Date:** 2026-08-13
- **Decides:** how the setter-facing "accepted-link" guide page keeps its three
  code-derived reference tables (recognized cage names, supported constraint
  types, supported sizes) and its per-constraint section from drifting away from
  the decoder — resolved on wayfinder map [#335](https://github.com/caneff/gridfind/issues/335),
  decision [#337](https://github.com/caneff/gridfind/issues/337).

## Context

The guide tells a setter how to build a SudokuMaker link gridfind will accept.
Three of its lists already live in the decoder: the recognized cosmetic-cage
names (`MARKER_LABELS`), the supported constraint types (`DECODER_REGISTRY`),
and the box-convention sizes (`BOX_SHAPE`). Hand-copied into a page, each list
lies the moment the code changes — the exact failure `CODING_STANDARDS.md`
names ("a stale comment lies").

Not every part of the page has a code home. How a setter *draws* a constraint in
SudokuMaker is knowledge about a third-party UI gridfind does not control and
cannot test; the intro, the state-under-test reading, and the troubleshooting
flow are cross-cutting narrative that hangs off no single constraint.

## Decision

**The page is a generated build product; the code is the source of truth for
everything that can drift.** A stdlib generator renders a hand-edited HTML
template into a committed page under `docs/`. The template is authored with
`string.Template` `$slot` placeholders — no Markdown renderer, no new
dependency. `just check` regenerates the page and fails on any git diff against
the committed copy, the same regenerate-and-verify-clean shape as
`ruff format --check`. The committed page stays self-contained static HTML, so a
setter can open it directly.

**Authority splits by what the code knows:**

| Page content | Source |
|---|---|
| Recognized cage-name → role table | `MARKER_LABELS`, imported |
| Supported constraint-type table | `DECODER_REGISTRY`, imported |
| Box-convention size table (`{4, 6, 9}`) | `BOX_SHAPE`, imported |
| Per-constraint facts: wire block, decode result, accept/ignore/reject | `setter_guide.SETTER_DOCS`, keyed by wire type |
| SudokuMaker draw-action per constraint | hand-written in the template |
| Intro, state-under-test reading, troubleshooting, "any square size needs its own regions" | hand-written in the template |

**`setter_guide.SETTER_DOCS` carries the per-constraint description, keyed by
wire type.** The setter-facing facts a reader would otherwise hand-copy — the
wire block, what it decodes to, and the accept/ignore/reject verdict — live in
a `SetterDoc` table keyed by the same wire-type integer `DECODER_REGISTRY` uses,
read only by `setter_guide.py`. Adding a constraint type therefore forces a row
in both tables. The two structural rows (`0` givens, `1` regions) are not
constraints a setter draws; they carry no `SETTER_DOCS` entry, and the generator
skips any wire type missing from the table — the absence marks a row as
not-setter-facing rather than relying on a separate skip-list.

## Considered options

- **Generated HTML fragment the page `include`s / a doc-build step that
  regenerates the tables.** Both need a build step and break the settled
  self-contained-static-HTML shape (#335) — heavy machinery for three tiny,
  rarely-changing lists.
- **A test that asserts a hand-written page matches the code.** Keeps the page
  hand-authored but leaves the tables and per-constraint prose to be written and
  maintained by hand; the generator route removes that authoring burden for
  everything the code already knows.
- **Hand-authored prose with a manual drift-check.** No enforcement — the "stale
  comment lies" failure relocated into HTML.
- **Markdown source + a renderer dependency.** Rejected once the code-owned
  split shrank the hand-written part to a few static paragraphs and the
  per-constraint draw-actions; a Markdown renderer is a dependency bought for
  very little. The narrative is written directly in the template as plain HTML.
- **Push the SudokuMaker draw-action into the code too.** Rejected: it is
  documentation for a UI gridfind neither owns nor can test, so co-locating it
  in the decoder only hides an unverifiable, drift-prone string.

## Consequences

- The generator (`setter_guide.py`) owns a `SetterDoc` table keyed by wire
  type, joined against `DECODER_REGISTRY` by that same key. The coupling is
  deliberate even split across two tables: both are keyed by wire type, so a
  new constraint type still forces a row in each, and a reader wondering why
  the setter guide holds per-constraint prose finds the answer here.
- The committed `docs/` page is a build artifact, never hand-edited; edits go to
  the template or the code. The `just check` diff guard is what makes that safe.
- The example gallery (static embed vs the `eval-links` server) is a separate
  open decision on #335, not settled here.
