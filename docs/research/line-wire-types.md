# SudokuMaker line-constraint wire-types

Research for [#663](https://github.com/caneff/gridfind/issues/663) (child of the
line-clue sub-map [#400](https://github.com/caneff/gridfind/issues/400)):
enumerate how each line-clue alias is encoded in a SudokuMaker `?puzzle=` link,
to inform the decode side of the line family.

Primary sources, in the ticket's priority order: (1) the real corpus links in
`src/gridfind/links/`, (2) the existing SudokuMaker decoders in
`src/gridfind/sudokumaker/`, (3) SudokuMaker's public format/docs on the web.
Each claim cites the source that owns it.

---

## Bottom line (read this first)

**No line-clue alias has any wire-type evidence in this repo.** Not one of
renban, German whisper, Dutch whisper, palindrome, between-line, lockout-line,
region-sum-line, sum-line / equal-sum, zipper, modular line, entropic line, or
greater-than chain appears:

- in any **corpus link** — `grep -riE 'renban|whisper|palindrome|between|lockout|region.?sum|zipper|modular|entropic|line'`
  over `src/gridfind/links/` (81 files) returns **nothing**;
- in any **decoder** — `DECODER_REGISTRY` (`src/gridfind/sudokumaker/registry.py`)
  and `wire_types.py` (`src/gridfind/sudokumaker/wire_types.py`) recognize **zero**
  line types;
- in the **accepted constraint map** (`docs/research/accepted-link-constraint-map.md`)
  — it documents only the types that appear in the corpus, and no line type is
  among them.

The **complete set of wire-`type` integers this repo has ever seen** (grep of
`src/` + `docs/` for `type <N>`) is:

`0, 1, 10, 11, 12, 13, 100, 101, 200, 201, 202, 300, 301, 305, 600, 601, 1000, 2000, 2001, 2003`

Every one is accounted for by a non-line constraint (table below). **There is no
gap in this list that a line type is known to fill.** So for the decode side of
the line family, the type numbers are an **open question that cannot be answered
from primary sources currently in reach** — they must be captured by generating
real links at sudokumaker.app (one per alias) and decoding them, which is app
interaction this research pass could not perform.

The **one thing the repo does settle** is the *shared line wire-format* the line
family will almost certainly inherit, because SudokuMaker already ships exactly
one ordered-path constraint — the **thermometer** — and it is fully decoded here.

---

## The shared line wire-format — the thermometer template (`type 300`)

The thermometer is SudokuMaker's only ordered-path block in the corpus, and it
is the template every line alias is expected to follow. This part **is**
repo-grounded.

- **Block shape:** `type 300` `{slow: bool, thermometers: [[cell indices, ordered, bulb first], …], style: {…}}`.
  A single block carries a **list of paths**, each path a flat list of raw cell
  indices. Source: `wire_types.py` `THERMO_TYPE = 300` docstring; confirmed against
  the real link `found-thermo-4x4` (two `type 300` blocks, one `slow:false`, one
  `slow:true`) — `docs/research/accepted-link-constraint-map.md` §3.3.
- **Ordered cell path storage:** the path is a **flat array of raw integer cell
  indices**, row-major (`i // N`, `i % N`), **order preserved** — bulb first.
  Order is the whole point of a line, in contrast to a `cage`'s unordered
  `cells`. Source: `src/gridfind/sudokumaker/cages.py` `thermo_constraints`
  (~L348-364) and `src/gridfind/sudokumaker/addresses.py` (`index_to_address` /
  `addresses`, "order preserved").
- **Index → address:** each raw index maps to an `RxCy` address via the shared
  `addresses(path, size)` seam (`addresses.py`), the same seam cages and marker
  cages use. Direction/order is preserved end-to-end into
  `Constraint("thermo", params={"path": [addr…], "slow": slow})`.
- **Per-block scalar parameters** ride at the **block level**, not per path:
  `slow` is read once and threaded onto every path in the block
  (`cages.py`). A cosmetic `style` object is present and **ignored**.
- **Contrast — edge clues do NOT store a path this way.** Kropki/XV (`type
  200/201/202`) store `clues: [{value, edge}]`, where `edge` is a single integer
  naming an orthogonally-adjacent **pair** (`_edge_to_pair`), not an ordered
  list. So "how a line stores its cells" is a genuinely different wire shape from
  "how an edge clue stores its pair" — lines follow the **thermo path** shape,
  not the edge shape. Source: constraint map §3.4-3.6.

**Inference (clearly marked as inference, not repo fact):** a line alias block
will most plausibly look like
`{<pathfield>: [[raw indices, ordered], …], style: {…}, <maybe a scalar param>}`,
i.e. a list of ordered raw-index paths at some type number, decoded through the
same `addresses()` seam as thermo, with any per-alias scalar (whisper threshold,
modular base) riding at the block level the way `slow` does. **The field name
and the type number are unknown** — thermo happens to call its list
`thermometers`; a line alias could use `lines`, `cells`, or an alias-specific
key, and only a real link will say which.

---

## Per-alias findings

`type` and path-field columns are **NO EVIDENCE** for every alias — the repo
carries none of them, and the reachable public docs (below) describe the puzzle
*rules* but never expose the built-in type numbers or JSON field names. The
"expected path storage" and "params" columns are **inference from the thermo
template + puzzle semantics**, not repo facts, and are flagged as such.

| Alias | Wire `type` (repo) | Ordered-path storage | Per-alias parameters | Evidence |
|---|---|---|---|---|
| **Renban** (consecutive set) | NO EVIDENCE | *infer:* ordered raw-index path, thermo-style (order actually irrelevant to the rule, but the wire still stores a path) | none expected — the rule is parameter-free (digits form a consecutive set) | none in repo/corpus/docs |
| **German whisper** | NO EVIDENCE | *infer:* ordered raw-index path | *infer:* threshold **may** be fixed (≥5) and carry no wire param, or ride as a block scalar like `slow`. Unknown. | none |
| **Dutch whisper** | NO EVIDENCE | *infer:* ordered raw-index path | *infer:* threshold ≥4; same open question as German — fixed vs. wire param unknown. May not be a distinct built-in at all (could be German-whisper-with-a-param). | none |
| **Palindrome** | NO EVIDENCE | *infer:* ordered raw-index path (**order load-bearing** — position i mirrors position n−i) | none expected | none |
| **Between line** | NO EVIDENCE | *infer:* ordered path; **endpoints are semantically special** (bulbs vs. body), so the wire may mark ends the way thermo marks the bulb by being first | none expected | none |
| **Lockout line** | NO EVIDENCE | *infer:* ordered path, endpoints special (diamonds) | *infer:* the "≥4 apart" endpoint gap could be fixed or a param. Unknown. | none |
| **Region-sum line** | NO EVIDENCE | *infer:* ordered path; **segmentation by box/region is derived from geometry at solve time, not stored** — the wire almost certainly stores just the path and lets region membership segment it | *infer:* none on the wire (segmentation is geometric) | none |
| **Sum-line / equal-sum** | NO EVIDENCE | *infer:* ordered path | *infer:* may carry a target sum scalar, or be the parameter-free "all segments equal" form | none |
| **Zipper** | NO EVIDENCE | *infer:* ordered path; **center is the pivot** — pairs equidistant from the middle sum to the center value, so order/midpoint is load-bearing | *infer:* none on the wire (center is positional) | none |
| **Modular line** | NO EVIDENCE | *infer:* ordered path | *infer:* **modular base** almost certainly a wire scalar (base 3 is the common form but the tool likely lets it vary) — expect a block-level `mod`/`base`-like field | none |
| **Entropic line** | NO EVIDENCE | *infer:* ordered path | *infer:* entropy grouping (low/mid/high 1-3/4-6/7-9) may be fixed for a 9-grid or parameterized for other sizes | none |
| **Greater-than chain** | NO EVIDENCE | *infer:* ordered path, **direction load-bearing** (strictly decreasing along the stored order) | none expected | none |

`NO EVIDENCE` = not present in any corpus link, not in any decoder, not in the
accepted constraint map, and not exposed by the reachable public docs.

---

## The non-line types the repo *does* know (for contrast / exclusion)

So a future session can see at a glance that none of these is a mislabeled line,
and which numeric neighborhoods are already taken. Source: `wire_types.py`,
`registry.py`, `frame.py`, and the accepted constraint map.

| `type` | Meaning | Ordered path? |
|---|---|---|
| `0` | classic ruleset (rows/cols/box implied) | no |
| `1` | region/box geometry (`regions` matrix) | no |
| `10` / `11` | negative `\` / positive `/` diagonal (global toggles) | no |
| `12` / `13` | anti-king / anti-knight (global toggles) | no |
| `100` / `101` | even / odd cells (`{cells, style}`) | no (unordered) |
| `200` / `201` | white / black kropki (`{clues:[{value, edge}], negative}`) | no (edge pairs) |
| `202` | XV (`{clues:[{value, edge}], negative}`) | no (edge pairs) |
| `300` | **thermometer** (`{slow, thermometers:[[…]]}`) | **YES — the template** |
| `301` | killer cage (`{cages:[{cells, value}]}`) | no (unordered) |
| `305` | windoku extra region (`{cells}`) | no (unordered) |
| `600` / `601` | 159-indexing row / col (`{cells, style}`) | no |
| `1000` | custom constraint (JS logic; recognized by `definition.name` only) | n/a |
| `2000` | cosmetic outline art (inert, dropped with warning) | n/a |
| `2001` | cosmetic cage (decoration; also the doubler/S-cell/Somedoku marker carrier) | no |
| `2003` | Schrödinger marker block (inert; the mode is a flag, not a wire signal) | n/a |

The 300-series (`300` thermo, `301` cage, `305` extra region) is the "drawn
region/path/cage" neighborhood; **if** line types cluster with their nearest
relative it would be near `300`, but that is a guess with **no** corroboration —
do not treat `302`/`303`/`304` as line types on the strength of this. Custom
line logic authored through the `type 1000` custom-constraint tool is a separate
matter (see gap #3).

---

## Gaps that could not be resolved from primary sources

1. **Every line type number is unknown.** No corpus link carries a line, so the
   ground-truth source the repo relies on for every *other* type is simply
   absent here. **To close it:** open sudokumaker.app, draw one puzzle per alias
   (renban, German whisper, palindrome, between, lockout, region-sum, sum,
   zipper, modular, entropic, greater-than), copy each `?puzzle=` link, and
   decode it offline (lz-string → JSON; the pipeline is documented in
   `docs/research/sudoku-link-formats.md` §4-5). Each decoded block's `type` and
   its path-field name is the missing datum. This is a ~1-hour capture task,
   blocked only on interacting with the live app. **Recommend making it a
   fixture-capture ticket under #400** — the same way every other type was
   nailed down (thermo via `found-thermo-4x4`, kropki via `found-kropki-4x4`).

2. **Public docs describe rules, not wire format.** SudokuMaker's format is
   "basically undocumented" by its own community's account
   ([kammer.xyz guide](https://kammer.xyz/blog/sudokumaker/)). The
   [aGnomadic link-generator gist](https://gist.github.com/aGnomadic/deb33ef8b6ac7860c3326908d7b8f06e)
   only demonstrates `type 1` (regions) and givens. The
   [Chris-Tophski/SudokuMakerConstraints](https://github.com/Chris-Tophski/SudokuMakerConstraints)
   repo documents the **custom-constraint (`type 1000`) JS API**, not the
   built-in constraint type numbers. So the numbers are not discoverable from
   docs — only from links.

3. **"Dutch whisper" and the whisper/threshold split are unconfirmed as
   distinct built-ins.** Dutch whisper (≥4) may be a first-class built-in, a
   parameterized German whisper, or only expressible as a `type 1000` custom
   constraint. Which one it is changes whether the decoder needs a distinct type
   or a threshold param. Resolve it with the same link-capture pass.

4. **Whether per-alias scalars ride the wire at all is unknown.** Thermo's
   `slow` proves block-level scalars exist, but whether a whisper carries its
   threshold, a modular line carries its base, or a region-sum carries anything
   (vs. deriving segmentation from geometry) is inference until a real link is
   decoded. The region-sum and zipper params in particular are most likely
   **positional/geometric, not stored** — but that too needs a link to confirm.

---

## Sources

- `src/gridfind/sudokumaker/wire_types.py` — the complete recognized type
  vocabulary (no line types).
- `src/gridfind/sudokumaker/registry.py` — `DECODER_REGISTRY` dispatch table.
- `src/gridfind/sudokumaker/cages.py` (`thermo_constraints`) and
  `src/gridfind/sudokumaker/addresses.py` — the thermo ordered-path decode, the
  line template.
- `src/gridfind/links/` — 81 corpus links; none carries a line
  (`grep -riE 'renban|whisper|palindrome|…'` → empty).
- `docs/research/accepted-link-constraint-map.md` §3.3-3.6 — thermo vs. edge-clue
  wire shapes, all corpus-confirmed.
- `docs/research/sudoku-link-formats.md` §4-5 — the SudokuMaker envelope and the
  offline lz-string decode pipeline (the tool for the capture task in gap #1).
- Public docs (rules only, no wire format): SudokuMaker user guide —
  https://kammer.xyz/blog/sudokumaker/ ; link generator gist —
  https://gist.github.com/aGnomadic/deb33ef8b6ac7860c3326908d7b8f06e ;
  custom-constraint (`type 1000`) library —
  https://github.com/Chris-Tophski/SudokuMakerConstraints ; app —
  https://sudokumaker.app/
