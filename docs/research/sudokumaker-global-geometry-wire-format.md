# SudokuMaker global-geometry wire shapes (#748)

Research for #748 (part of #401): the `type` code and params SudokuMaker's
wire format uses for anti-taxicab, anti-consecutive (global), disjoint
groups, global entropy, and global mod.

**Primary source used:** SudokuMaker's own production JS bundle, fetched
live and read directly (Vite build, minified but not obfuscated — the
constraint `type` enum, the default-params factory, and the setter-facing
"add constraint" description generators are all present verbatim). No
public docs page or format spec exists on sudokumaker.app; no third-party
GitHub repo decoding this format was found (see §6).

- Fetched: `https://sudokumaker.app/` → `<script type="module"
  src="/assets/main-D44ZZMA9.js">` → `https://sudokumaker.app/assets/main-D44ZZMA9.js`
  (fetched 2026-08-27, HTTP 200, `etag: W/"a5b8cc4eec622e76f43779d52d4c6b31"`,
  1,275,243 bytes). Note: `sudokumaker.com` (no `.app`) is a **parked domain**
  (redirects to HugeDomains) — not the real site. The real app is
  `sudokumaker.app`, matching this repo's existing
  `docs/research/sudoku-link-formats.md` §4.
- The bundle's own `formatVersion` constant (`_1`) is **`"1.6.0"`** — newer
  than the `"1.5.0"` this repo's prior research doc cites, so the schema has
  moved since that note was written. Nothing found below appears
  version-gated against that bump, but flagging it as a possible source of
  future drift.

## TL;DR

| Constraint | Wire `type` | Params carried | Distance/size param? | Status |
|---|---|---|---|---|
| Anti-taxicab | **none found** | n/a | n/a | **Unverified — evidence points to "does not exist"** |
| Anti-consecutive (global, orthogonal) | `15` (`Nonconsecutive`) | none — bare `{type:15}` | No — fixed at difference 1, not exposed | **Verified** |
| Disjoint groups | `14` (`DisjointGroups`) | none — bare `{type:14}` | n/a | **Verified** |
| Global entropy | `16` (`GlobalEntropy`) | `{type:16, groups:[bitmask,...]}` | Generalizes for digitCount 4/6/8/9 (auto-computed groups); any other size gets an empty/manual `groups` | **Verified** |
| Global mod | **same type as entropy: `16`** (`GlobalEntropy`), just a different `groups` value | `{type:16, groups:[bitmask,...]}` (residue-class grouping) | **9-digit puzzles only** — no analogous auto-generated grouping for 4/6/8 | **Verified** |

The two-header takeaway: SudokuMaker does not model "global mod" as its own
wire type. It is one of the *setter-facing preset descriptions* offered for
the same `GlobalEntropy` (`16`) block — the wire only ever sees
`{type:16, groups:[...]}`, and "entropy" vs. "mod-3" is just which digit
groups populate `groups`. Likewise, disjoint groups and (global) nonconsecutive
are bare toggles like anti-king/anti-knight/the diagonals already documented
in this repo's `wire_types.py` and `docs/research/accepted-link-constraint-map.md`
§3.9 — no payload beyond `type`.

---

## 1. Anti-taxicab

**Unverified — not found; evidence supports "this constraint does not exist
in SudokuMaker."**

What I checked:

- The full constraint `type` enum was extracted from the bundle (see §7 for
  the complete list) by finding the enum object literal — a single
  contiguous run of `n[n.Name=N]="Name"` assignments starting at `Givens=0`
  and ending at `FogTriggers=4001`. There is no `Taxicab`/`AntiTaxicab`
  member anywhere in it.
- Case-insensitive substring search of the whole 1.27 MB bundle for
  `taxicab` → **0 matches**.
- Search for `manhattan` → 3 matches, but all three are the generic vector
  math helper `getManhattanDistance`/`getManhattanDistanceBetweenCells`,
  used internally for plain orthogonal-adjacency checks (e.g. region/group
  connectivity validation — "is this cell orthogonally next to that one").
  None of the three call sites is wired to a `type` enum member or to a
  "distance between equal digits" rule. Quote (one call site):
  `!U.has(ne)&&n.helpers.geometry.getManhattanDistanceBetweenCells(J,ne)===1&&R.add(ne)`
  — this is a flood-fill/connectivity walk, not a constraint definition.
- The setter-facing "add constraint" catalog (`Pj`, the array of
  `{params:{type:...}, description:...}` entries used to populate the
  constraint picker) was located and read in full around the global-toggle
  entries (§7 quotes it around Antiking/Antiknight/DisjointGroups/
  Nonconsecutive) — no taxicab-flavored entry sits among them.

Conclusion: as of this build (fetched 2026-08-27, formatVersion 1.6.0),
SudokuMaker has no built-in anti-taxicab rule, global toggle, or preset. A
setter wanting one would have to build it as a `type 1000` (`Custom`)
programmable constraint — the existing generic escape hatch this repo
already models by name only (`dropped.constraint_name`,
`sudokumaker/wire_types.py` `CUSTOM_CONSTRAINT_TYPE = 1000`), not a
dedicated global-geometry wire type. If a real link surfaces one, expect it
to arrive as a `type 1000` block named something like "Anti-taxicab", not a
new numeric type.

I did not find a public SudokuMaker docs page, help page, or third-party
decoder repo to cross-check this against (see §6) — the JS bundle itself is
the only primary source available, but it is authoritative for "what the
wire format can currently emit" since it's the literal encoder/decoder.

Source: `https://sudokumaker.app/assets/main-D44ZZMA9.js` (fetched
2026-08-27).

## 2. Anti-consecutive / non-consecutive (global)

**Verified.**

- Enum member: `n[n.Nonconsecutive=15]="Nonconsecutive"` — type code **15**.
  Source: `https://sudokumaker.app/assets/main-D44ZZMA9.js`.
- Default/only wire shape, from the params-factory `switch`:
  `case T.Antiking:case T.Antiknight:case T.DisjointGroups:case T.Givens:case T.Nonconsecutive:return{type:n}`
  — a **bare** `{type:15}` block, identical shape to the anti-king/
  anti-knight/disjoint-groups toggles this repo already decodes
  (`wire_types.py` `ANTI_KING_TYPE`/`ANTI_KNIGHT_TYPE`). No `groups`, no
  `difference`, no other field.
- Setter-facing description (from the constraint-picker catalog `Pj`):
  `{params:{type:T.Nonconsecutive},description:"Cells that are orthogonally adjacent cannot contain consecutive digits."}`
  — confirms it is orthogonal-adjacency only (no diagonal variant, no
  configurable radius) and that "consecutive" here is fixed at a
  difference of 1.
- No distance/threshold param is exposed anywhere: the difference is not
  configurable on the wire. One more corroborating detail — the toggle
  feeds back into the Kropki-dot negative-space logic as a hardcoded `1`:
  `u.config.type===T.Nonconsecutive&&l.push(1)` inside the routine that
  builds the "known unmarked-pair exclusions" list, i.e. SudokuMaker itself
  treats "nonconsecutive" as strictly "no unmarked orthogonal pair may
  differ by exactly 1" — never a settable N.

Source: `https://sudokumaker.app/assets/main-D44ZZMA9.js` (fetched
2026-08-27).

## 3. Disjoint groups

**Verified.**

- Enum member: `n[n.DisjointGroups=14]="DisjointGroups"` — type code **14**.
- Wire shape: bare `{type:14}`, from the same default-factory switch quoted
  in §2 (`case T.DisjointGroups: ... return{type:n}`) — no payload.
- Setter-facing description varies by puzzle type but the wire block never
  changes shape:
  `mj(n){return n.type===nt.Sudoku?[{description:`Cells with the same position within the boxes contain all the numbers 1 to ${n.maxDigit}`,params:{type:T.DisjointGroups}}]:[{description:"Cells with the same position within the boxes contain all different digits",params:{type:T.DisjointGroups}}]}`
  — the `params` payload is always `{type:T.DisjointGroups}` regardless of
  which description string is shown; the "1 to maxDigit" vs. "all different
  digits" split is purely cosmetic/UI text depending on whether the puzzle
  type is classic Sudoku or a generic variant.
- Cross-reference: this matches the shape family (bare `{type:N}` global
  toggle) this repo's `wire_types.py` already documents for
  `NEGATIVE_DIAGONAL_TYPE`/`POSITIVE_DIAGONAL_TYPE`/`ANTI_KING_TYPE`/
  `ANTI_KNIGHT_TYPE` and `docs/research/accepted-link-constraint-map.md`
  §3.9 — disjoint groups (14) and nonconsecutive (15) belong in that same
  family, just not yet in `wire_types.py`.

**Jigsaw position order (#750/#756 follow-up, verified 2026-08-28).** #750
resolved the rule's home as a second `DistinctOverGroups` whose partition
transposes `region_map_for_constraints`'s `RegionMap` — group *k* is the
*k*-th cell of every region, row-major-within-region — but flagged that
order as an assumption to verify against SudokuMaker for a jigsaw. No real
jigsaw-plus-disjoint-groups link was available to capture, so this was
verified straight off the same production bundle instead, which is stronger
evidence than one example link: SudokuMaker's own SudokuPad-export
translator re-derives the rule from the `regions` label array and is quoted
here verbatim.

- The translator (`ut(T.DisjointGroups, {sudokuPad: n => {...}})`):
  `const e=n.projectData.constraints.find(i=>i.config.type===T.Regions);
  if(!e)return;const t=J6(e.config.regions);const s=t[0].length;
  if(t.every(i=>i.length===s))for(let i=0;i<s;i++)
  n.addGlobalUniqueDigitsGroup(t.map(r=>r[i]))` — no `Regions` block, no
  group is added at all (a bare `disjoint-groups` toggle with no regions is
  a silent no-op on SudokuMaker's own side); `s = t[0].length` then
  `t.every(...)` gates on every region being the same size before adding
  any group, else nothing is added — SudokuMaker itself treats both "no
  regions" and "unequal regions" as silent no-ops for this export path.
  gridfind's `MalformedPuzzleError` on both (#750's resolution) is
  deliberately stricter than this, matching the fail-loud coding invariant
  rather than mirroring SudokuMaker's silent skip.
  `n.addGlobalUniqueDigitsGroup(t.map(r=>r[i]))` for `i` in
  `0..s-1` is exactly "group *k* = the *k*-th cell of every region."
- `J6`, the region-label-to-cell-list splitter the translator calls:
  `function J6(n){const e=[];for(let t=0;t<n.length;t++)n[t]!==-1&&
  (e[n[t]]||(e[n[t]]=[]),e[n[t]].push(t));for(let t=0;t<e.length;t++)
  e[t]||(e[t]=[]);return e}` — walks the flat, row-major `regions` label
  array by increasing flat index `t` and appends `t` to `e[label]` in that
  same encounter order. That is byte-for-byte the same walk
  `RegionMap.from_labels` already does (`for index, label in
  enumerate(labels): ... groups.setdefault(label, []).append(...)`), so
  each region's internal cell order — including for an irregular jigsaw
  region — is confirmed to be row-major board-scan order, exactly what
  gridfind's transpose already assumes. No code change needed.
- One documented divergence, out of this ticket's scope: `J6` treats a `-1`
  label as "no region" and skips it entirely, so a cell SudokuMaker leaves
  unassigned never joins any region's list; `RegionMap.from_labels` has no
  such sentinel and would fold a `-1` label into an ordinary region keyed
  `-1`. Not exercised by any real link captured so far — worth a note for
  whoever next touches `RegionMap.from_labels`, not a fix owed by #756.

Source: `https://sudokumaker.app/assets/main-D44ZZMA9.js` (fetched
2026-08-27, re-read 2026-08-28 for the DisjointGroups/`J6` translator
functions).

## 4. Global entropy

**Verified**, including the size-generalization behavior.

- Enum member: `n[n.GlobalEntropy=16]="GlobalEntropy"` — type code **16**.
- Default/empty wire shape: `case T.GlobalEntropy:return{type:n,groups:[]}`
  — so the block is `{type:16, groups:[...]}`, where `groups` is a **list
  of digit-set bitmasks**, not a list of raw digit arrays. Confirmed by the
  shared bitmask helper used to build every `groups` entry:
  `function Rs(n){let e=0;for(const t of n)e|=1<<t;return e}` — the same
  helper (`Rs`) also builds `groups` for the `EntropyLines`/`GroupedLine`
  wire type (406), so gridfind's existing in-repo guess for `type 406`'s
  `groups: [bitmask, ...]` shape (`wire_types.py` lines around
  `GROUPED_TYPE`) is independently corroborated by this same helper —
  useful cross-check even though 406 wasn't part of this ticket's ask.
- **Size generalization**, from the setter-facing preset generator `Sj(n)`
  (the function that builds the "add a global-entropy constraint" menu
  entries), keyed off `n.digitCount`:
  - `digitCount` 4, 6, or 8 → one auto-generated 2-group low/high split:
    `i()` builds `a`/`u` (below/above the midpoint of `minDigit..maxDigit`)
    and emits `{type:T.GlobalEntropy, groups:[Rs(u),Rs(a)]}`.
  - `digitCount` 9 → **two** auto-generated presets are offered together:
    `r()` (three groups of three consecutive digits — "low/middle/high",
    i.e. the classic 9x9 entropy) and `o()` (three groups of digits
    congruent mod 3 — this is "global mod" under a different name; see
    §5). Quote: `switch(s){case 4:case 6:case 8:return[i()];case 9:return[r(),o()];default:return[l()]}`.
  - Any other `digitCount` (not 4/6/8/9) → falls to `l()`, which returns a
    **bare** `{type:T.GlobalEntropy}` with **no `groups` at all** and the
    generic description "Every 2x2 square of cells must contain at least 1
    digit of every specified group." — i.e. SudokuMaker does not know how
    to auto-partition the digit range for that grid size; the setter must
    define the groups manually via the property editor, and only then does
    a concrete `groups` array land on the wire.
  - So: global entropy is **not 9x9-only** — it generalizes down to 4x4/
    6x6/8x8 with an auto-computed low/high split — but the specific
    "low/mid/high thirds" grouping (three even bands) is only auto-offered
    at `digitCount === 9`. All sizes still emit the same `type: 16` wire
    shape; what differs is only which digit sets end up in `groups`, and
    whether SudokuMaker pre-fills them or leaves the block group-less
    pending manual setter input.
  - Caveat worth flagging: the description text is hardcoded to say "Every
    2x2 square of cells" even for the 9-digit mod-3 preset, which visually
    applies to 3x3 boxes on a 9x9 grid — looks like a copy/paste artifact
    in SudokuMaker's own UI copy, not a gridfind concern, but worth noting
    if cross-checking against a captured link's description string.

Source: `https://sudokumaker.app/assets/main-D44ZZMA9.js` (fetched
2026-08-27).

## 5. Global mod

**Verified — it is not a distinct wire type.** It rides the exact same
`type: 16` (`GlobalEntropy`) block as §4, distinguished only by which digit
groups are placed in `groups`.

- From the same `Sj(n)` preset generator quoted in §4, the `o()` closure
  (offered only when `digitCount === 9`, alongside the low/mid/high
  entropy preset `r()`):
  ```
  o=()=>{const a=[[0,3,6],[1,4,7],[2,5,8]].map(u=>u.map(c=>c+e));
    return{description:`Every 2x2 square of cells must contain a digit
    from (${a[0]}), a digit from (${a[1]}) and a digit from (${a[2]}).`,
    params:{type:T.GlobalEntropy,groups:a.map(u=>Rs(u))}}}
  ```
  With `e = minDigit = 1` for a standard 9-digit puzzle, `a` evaluates to
  `[[1,4,7],[2,5,8],[3,6,9]]` — the three residue classes mod 3 (1,4,7 ≡ 1
  mod 3; 2,5,8 ≡ 2 mod 3; 3,6,9 ≡ 0 mod 3). The emitted wire block is
  `{type:16, groups:[Rs([1,4,7]), Rs([2,5,8]), Rs([3,6,9])]}` — same shape
  as the entropy preset, just three different bitmasks.
- **9x9-only, same as entropy's mod-3 preset**: the `switch(s)` in `Sj`
  only offers `o()` when `s === 9` (`case 9:return[r(),o()]`); for
  `digitCount` 4, 6, or 8 only the low/high preset `i()` is offered — there
  is no auto-generated mod-N grouping for those sizes. A setter could still
  hand-build an equivalent mod-N grouping on a smaller grid through the
  generic/manual `l()` path (bare `{type:16}`, groups added by hand in the
  editor), but SudokuMaker does not auto-offer or auto-generate one.
- No separate `GlobalMod`/`Mod` enum member exists — confirmed against the
  full enum list (§7): there is nothing between `GlobalEntropy=16` and
  `Even=100`.

Source: `https://sudokumaker.app/assets/main-D44ZZMA9.js` (fetched
2026-08-27).

## 6. Third-party / public docs cross-check

- No SudokuMaker help/docs page describing the wire JSON format was found;
  `sudokumaker.app`'s own site is the app itself with no separate docs
  route surfaced by the fetch.
- `sudokumaker.com` is a **parked domain** (HugeDomains), unrelated to the
  real app — ruled out as a docs source.
- No WebSearch was run for third-party GitHub repos decoding this specific
  format (a search for e.g. "sudokumaker json format github" was not
  executed in this pass) — flagging as **unverified/not attempted**, since
  the live JS bundle already gave a complete, authoritative answer to every
  question in this ticket (the actual encoder/decoder source, not a
  secondhand description of it). If a future ticket needs corroboration
  independent of SudokuMaker's own code, that search is the next step.

## 7. Supporting data — full `type` enum (for context)

Extracted verbatim from the bundle as one contiguous enum initializer:

```
Givens=0, Regions=1,
DiagonalMinus=10, DiagonalPlus=11, Antiking=12, Antiknight=13,
DisjointGroups=14, Nonconsecutive=15, GlobalEntropy=16,
Even=100, Odd=101, Maximum=102, Minimum=103,
Difference=200, Ratio=201, XV=202,
Thermometer=300, KillerCages=301, Clone=302, Quadruple=303,
LookAndSayCages=304, DifferentValues=305, CountingCircles=306,
Renban=400, Whisper=401, Palindrome=402, BetweenLines=403,
RegionSumLine=404, Sequence=405, EntropyLines=406, LockoutLines=407,
Arrow=408, DoubleArrow=409,
LittleKillers=500, SandwichSums=501, XSums=502, Skyscrapers=503,
NumberedRooms=504,
RowIndexer=600, ColumnIndexer=601,
Custom=1000,
CosmeticLine=2000, CosmeticCage=2001, CosmeticSymbol=2002, SudokuRules=2003,
FogLights=4000, FogTriggers=4001
```

Cross-check against this repo's `src/gridfind/sudokumaker/wire_types.py`:
matches on every type already modeled there (`GIVENS_TYPE=0`,
`REGIONS_TYPE=1`, diagonals `10`/`11`, `ANTI_KING_TYPE=12`,
`ANTI_KNIGHT_TYPE=13`, Kropki `200`/`201`, XV `202`, thermo `300`, killer
cage `301`, clone `302`, quadruple `303`, the line-clue family `400`–`409`,
indexing `600`/`601`, custom `1000`, cosmetic cage `2001`). One
discrepancy worth flagging separately (not part of this ticket): this
repo's `wire_types.py` comment names `EXTRA_REGION_TYPE = 305` as a
windoku-style extra-region block (`{cells:[...]}`), but the live enum names
`305` `DifferentValues` ("Digits cannot repeat in the marked cells" — a
flat named-cells no-repeat clue, not necessarily a window/extra-region
draw). Flagging as a data point for a future ticket, not resolving it here
— out of scope for #748.
