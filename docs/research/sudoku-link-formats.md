# Sudoku puzzle-sharing link formats (SudokuPad / f-puzzles / SudokuMaker)

Research for the design question: *is "paste a link → decode into a puzzle
definition" a cheap deterministic offline decode or a hard/network task, and can
such links carry a solver's in-progress state?*

Primary sources are the tools' own source code (the SudokuPad puzzle loader,
which does the real decoding) plus the lz-string reference. Cited inline.

---

## Bottom line

- **(a) Decode difficulty — mostly cheap & deterministic, offline.** The
  *self-contained* link forms (SudokuPad `scl`/`ctc`/`fpuz`/`fpuzzles`/`scf`,
  f-puzzles links, and SudokuMaker `?puzzle=`) embed the entire puzzle in the URL
  as **lz-string-compressed JSON**. Decoding is a pure, deterministic,
  offline pipeline: strip a short prefix → URI-decode → lz-string decompress →
  (un-minify / format-map) → JSON. No headless browser, no server. A Python port
  of lz-string exists (`lzstring` on PyPI), and the remaining steps are plain
  string/JSON transforms.
  **The one exception is SudokuPad *short/custom ids*** (e.g.
  `sudokupad.app/tuesday-puzzle`): these are *not* self-contained — they require
  a network round-trip to `https://sudokupad.app/api/puzzle/<id>` to fetch the
  real payload, which then decodes offline as above.
- **(b) Working state — CORRECTED: SudokuMaker links DO carry the solver's
  in-progress state.** *(Original finding below claimed definition-only; that was
  wrong for SudokuMaker, disproven by decoding two real links on 2026-08-06.)* A
  SudokuMaker `?puzzle=` link encodes, per cell: `given:true`+`value` (a setter
  clue), `value` alone (a solver placement), `candidates` (a digit bitmask =
  solver pencilmarks), `cornerPencilMarks`, and `colors` — i.e. the puzzle
  definition **and** the live solve, cleanly separated by the `given` flag. So a
  SudokuMaker link is sufficient to reconstruct both a `Puzzle` and a
  `WorkingState`.
  - *Still likely definition-only (UNVERIFIED for state):* SudokuPad / f-puzzles
    **share** exports. The f-puzzles cell schema *has* `centerPencilMarks` /
    `cornerPencilMarks` / `candidates` fields, so state is representable, but
    whether the share/export URL populates them from a live solve was not
    confirmed — treat as open until decoded, the same way SudokuMaker was.

---

## 1. SudokuPad URL formats & encoding

SudokuPad's own loader (`puzzleloader.js`) is the authoritative decoder. Two
distinct kinds of `puzzleId` after `sudokupad.app/`:

**Self-contained (offline-decodable).** A `puzzleId` beginning with a known
format prefix carries the whole puzzle. Registered prefixes (with aliases):

| Prefix | Alias | Payload after prefix |
|--------|-------|----------------------|
| `scl`  | `ctc` | lz-string-compressed, `PuzzleZipper`-minified SudokuPad SCL JSON |
| `fpuz` | `fpuzzles` | lz-string-compressed f-puzzles JSON (converted to SCL on load) |
| `scf`  | —     | "Sudoku Compressed Format": bit/char-packed classic givens (`codoku`/`dedoku`), optional `*`-separated constraints |

Decode pipeline (`decompressPuzzleId`): `stripPuzzleFormat` → `saveDecodeURIComponent`
→ `fixFPuzzleSlashes` → `saveDecompress` (lz-string). Then per-format parse:
`parsePuzzleScl` = `PuzzleZipper.unzip` → JSON; `parsePuzzleFpuz` =
`JSON.parse` → `loadFPuzzle.parseFPuzzle` (f-puzzles→SCL); `parsePuzzleScf` =
`PuzzleTools.decodeSCF`.

**Short / remote ids (network-dependent).** Any `puzzleId` that matches *no*
known prefix is treated as remote (`isRemotePuzzleId` returns true) and must be
fetched from a server before it can be parsed. The loader tries, in order:

```
https://sudokupad.app/api/puzzle/<id>                                    (local API)
https://sudokupad.svencodes.com/ctclegacy/<id>                           (legacy proxy)
https://firebasestorage.googleapis.com/v0/b/sudoku-sandbox.appspot.com/o/<id>?alt=media
```

The fetched body is itself an scl/fpuz payload (the loader wraps a raw remote
puzzle as `scl` + `compressPuzzle(...)`). So a short link = **one HTTPS GET, then
offline decode**. You cannot resolve a short id without the network (or your own
mirror of that API).

**Encoding = lz-string.** `compressPuzzle`/`decompressPuzzle` are lz-string's
`compressToBase64`/`decompressFromBase64` (`fpuzzlesdecoder.js`, with a
base64-ish alphabet `A–Za–z0–9+/\`). This is the same lz-string family f-puzzles
uses. Not deflate, not plain base64 — lz-string specifically.
(lz-string reference: pieroxy.net.)

`PuzzleZipper` (`puzzlezipper_lib.js`) is a JSON *minifier* applied to SCL before
compression: it shortens keys (`cells`→`ce`, `value`→`v`, `regions`→`re`,
`cages`→`ca`, `color`→`c`, `title`→`t`, …), unquotes object keys, encodes
`true`/`false` as `t`/`f`, and shortens hex colors. `unzip` reverses it. Pure
string transform, trivial to reimplement.

## 2. Decoded schema

**SudokuPad SCL / CTC** (the canonical internal format; f-puzzles and Penpa both
get converted *into* it). Top-level object roughly:
`{ id, cells: [[ {value, given, …} × cols ] × rows], regions: [...],
cages: [{cells:[[r,c],…], value, type, …}], … }` — plus arrays of overlay/glyph
and rules objects. `cells` is a 2-D grid; `regions` gives the box/region
partition; `cages` carry both killer-style cages and general variant constraints;
a rules/ruleset text describes the puzzle in prose.

**f-puzzles JSON** (`parseFPuzzle` maps every field). Cell grid + constraint
arrays:
- `size` (grid dimension, e.g. 9), `grid: [[ cell ]]` where a cell has
  `value`, `given` (bool), `region`, and optional `centerPencilMarks`,
  `cornerPencilMarks`, `candidates`, `c`/highlight.
- `title`, `author`, `ruleset`, `solution`.
- Constraint arrays observed in the decoder: `littlekillersum`, `arrow`,
  `thermometer`/`line`, `killercage`/`cage`, `betweenline`, `quadruple`,
  `clone`, `extraregion`, `odd`, `even`, `minimum`, `maximum`, `circle`,
  `rectangle`, `text`, `negative`, plus `metadata`.

**Minimal classic 9×9 complexity.** In f-puzzles it's just
`{size:9, grid:[[…81 cells…]]}` where givens are `{value:n, given:true}` and empty
cells are `{}` — a few hundred bytes of JSON that lz-string crushes to a short
token. The `scf` form is far more compact still: essentially the 81-char given
string packed via `dedoku` (empties run-length-collapsed), no per-cell JSON. So a
plain sudoku is cheap in every format; payload size grows with variant
constraints, not with the grid.

## 3. Solver working-state — definition only

No standard shareable link carries a *solver's* pencilmarks/tentative digits:

- **f-puzzles / SudokuPad share links** serialize the puzzle **definition**
  (givens, region layout, constraints, rules, and any *setter-authored* given
  pencilmarks). The dclamage f-puzzles integration notes confirm "given
  pencilmarks" are an authoring feature rendered distinctly from a solver's
  normal center marks.
- A solver's in-progress candidates/placements are held **client-side**
  (localStorage / app progress state), not embedded in the puzzle URL you share.
  The f-puzzles cell object *has* `centerPencilMarks`/`cornerPencilMarks`/
  `candidates` fields, so a full board state is *representable* in the schema —
  but the share/export link is the setting-mode definition, not a live solve.

Practical takeaway for the constraint-solver project: decoding a link gives you a
clean puzzle definition to load; you will **not** get (nor need to round-trip) a
human solver's partial working state.

## 4. SudokuMaker (sudokumaker.app)

Distinct tool with its **own** JSON schema (not f-puzzles, not SCL), but the same
transport idea. URL: `https://sudokumaker.app/?puzzle=<payload>`, where payload
is `LZString.compressToEncodedURIComponent(json)` — self-contained, offline,
lz-string, same family as the others. Schema (v"1.5.0"):
`{ formatVersion:"1.5.0", puzzle:{ cells:[{given, value}, …],
constraints:[{type, regions:[…flattened region-id matrix…]}, …] } }`.
So: cells array + typed constraint objects (region layout is a constraint of a
given `type` whose `regions` is a flattened per-cell region-id matrix).
Relationship to f-puzzles/SudokuPad: shared *lineage* (variant-sudoku setting
tools, lz-string transport) but a **separate, non-interchangeable format** —
decode it with its own schema, not the f-puzzles/SCL mapping.
(Source: reverse-engineered link generator, aGnomadic gist, confirmed against
sudokumaker.app.)

## 5. Python decode difficulty

Deterministic and offline for all self-contained forms. Building blocks:

- **lz-string layer:** `lzstring` on PyPI (v1.0.4, "lz-string for python") ports
  `decompressFromBase64` / `decompressFromEncodedURIComponent`. Handles the
  f-puzzles and SudokuMaker payloads directly; SudokuPad's alphabet has a
  one-char tweak (`\` where standard uses `=`) that's a trivial adjustment.
- **PuzzleZipper unzip** (SCL): a handful of regex substitutions — reimplement in
  ~30 lines from `puzzlezipper_lib.js`.
- **f-puzzles → grid** and **scf `dedoku` unpack:** pure string/JSON logic,
  directly portable from `fpuzzlesdecoder.js` / `puzzletools.js`.

No headless browser or JS runtime is required for self-contained links. The only
network dependency is resolving a SudokuPad **short/custom id**, which needs one
GET to `sudokupad.app/api/puzzle/<id>` (or you accept only fully-encoded links).
There is no single pip-installable "SudokuPad link → JSON" package; you compose
`lzstring` + a small port of the above. The reference JS to port lives in the
SudokuPad `sudokutools` repo and marktekfan's `sudokupad-penpa-import`.

---

## Sources

- SudokuPad loader/decoder source (authoritative): `puzzleloader.js`,
  `fpuzzlesdecoder.js` — https://github.com/marktekfan/sudokupad-penpa-import
- SudokuPad tooling & format code: `sudokutools` (`puzzlezipper_lib.js`,
  `fpuzzlesdecoder.js`, `puzzletools_lib.js`, `compression/`) —
  https://github.com/SudokuPad/sudokutools /
  https://github.com/SudokuPad/sudokutools/blob/main/README.md
- Penpa→SCL converter (SCL as SudokuPad's target format) —
  https://github.com/marktekfan/penpa-to-scl
- lz-string reference (compression + URI-safe base64 encoders) —
  https://pieroxy.net/blog/pages/lz-string/index.html
- f-puzzles integration / given-pencilmarks semantics —
  https://github.com/dclamage/SudokuSolver/wiki/fpuzzles-integration
- SudokuMaker link format (reverse-engineered generator) —
  https://gist.github.com/aGnomadic/deb33ef8b6ac7860c3326908d7b8f06e ;
  app: https://sudokumaker.app/
- Python lz-string port — https://pypi.org/project/lzstring/
- SudokuPad app — https://sudokupad.app/
