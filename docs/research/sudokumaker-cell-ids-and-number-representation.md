# SudokuMaker cell ids and numeric representation

Research verified 2026-08-31 via the SudokuMaker app bundle plus live
in-app probes. Full probe table and the shared regression test live in the
`sudokumaker-custom-constraints` repo, issue #276 and commit `60a2c2f`. The
API row for `getCellAt` is documented in that repo's `docs/puzzle-api.md`.

## TL;DR

- `puzzle.getCellAt(col, row)` returns `id = col + row * width` (0-based),
  and `undefined` off-board — matches the bundle's `getIdFromCoordsSafe`.
  Watch the argument order: `row * width + col` is wrong and has been
  documented as "verified" before, silently transposing frames on
  non-symmetric boards.
- A cell id you compute yourself — via `getCellAt` or your own
  `width`-based arithmetic — is numerically `===` to a drawn group's id,
  but costs the solver ~1.3x per candidate read unless you coerce it with
  `| 0` first. The cause is the JS engine's internal numeric
  representation, not the API. Always coerce a derived id with `| 0`
  before handing it to a constraint component.

---

## 1. `getCellAt` coordinate mapping

`puzzle.getCellAt(col, row)` maps 0-based coordinates to a cell id as
`id = col + row * width`, returning `undefined` for a coordinate pair off
the board. This matches `getIdFromCoordsSafe` in the app bundle.

**Argument-order gotcha:** several backends had documented this call as
`row * width + col` and marked it "verified" — wrong argument order,
silently building transposed frames. This stayed hidden because it's
harmless when the built shape is symmetric; it only shows up on
non-symmetric boards.

## 2. Derived ids need `| 0` coercion

Cell ids are plain integers. But an id derived from the board size — via
`getCellAt`, or via your own arithmetic on `puzzle.spec.size.width` — is
numerically equal (`===`) to the id a drawn group carries, yet costs the
app's solver about 1.3x per candidate read. Coercing with `| 0` before
handing any derived id to a constraint component closes the whole gap. The
cause is the JS engine's internal numeric representation of the value, not
the API itself.

Probe results (regardless of registration order or array rebuilding):

| Id source | Time |
|---|---|
| Drawn-group id | ~2100ms |
| Size-derived id via `getCellAt`, no coercion | ~2700-2800ms |
| Size-derived id via own `r + c*width` arithmetic | ~2700-2800ms |
| Size-derived id via `getCellAt`, coerced with `\| 0` | ~2100ms |

**Rule of thumb:** any cell id your code computes rather than reads
verbatim from a drawn group should be coerced with `| 0` before it reaches
a constraint component.

## 3. Cross-reference

Full probe table and the shared regression test live in the
`sudokumaker-custom-constraints` repo:

- Issue #276, commit `60a2c2f`.
- `docs/puzzle-api.md` (the `getCellAt` API row).
- `examples/_shared/global-backends.test.mjs` (shared regression test).
