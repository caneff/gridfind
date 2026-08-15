# Accepted-link constraint map (SudokuMaker → gridfind)

Reference for the "accepted-link setter guide" webpage — wayfinder **map #335**,
ticket **#336**. It answers, for every board size and constraint gridfind
supports: what a setter draws in SudokuMaker, the wire block that produces,
how the decoder reads it, and the exact accept / ignore / reject boundary.

The authority is the decoder source, `src/gridfind/sudokumaker.py`, read
field-by-field. Every claim below cites `sudokumaker.py:NNN` or the ADR/doc it
came from. **Code wins over prose** — where the CONTEXT.md glossary disagrees
with the decoder, the decoder is right and the glossary is flagged.

---

## Bottom line

- **Post-migration form only.** Named cosmetic cages are now the *only* channel
  for declaring doublers and S-cells. The old **color / red-bit** channel and
  the `--schrodinger` / `--doubler` CLI flags are **retired** (issue #328).
  Variants are inferred from a `type 2001` block's top-level `name`, never
  sniffed from a color or declared out of band
  (`sudokumaker.py:32-39`, `sudokumaker.py:226-249`). The red bit survives only
  as a *witness-write* cosmetic so a human sees red S-cells/modifiers on an
  emitted solution link — the decoder never reads it (`sudokumaker.py:91-97`,
  `sudokumaker.py:385-413`).
- **Any square N decodes; boxes are a convention for N ∈ {4, 6, 9}.** Size and
  domain are read from the link's own headers, so a 4×4, 6×6, or 9×9 all decode
  through one path (`sudokumaker.py:322-350`, `sudokumaker.py:362-373`). Box
  geometry (the "classic regions" a bare `type 1` stands for) is defined only
  where `BOX_SHAPE` is — `{4: (2,2), 6: (2,3), 9: (3,3)}`
  (`layers/regions.py:64`); on any other N a `type 1` matrix always rides as an
  explicit jigsaw partition.
- **Three verdict-outcomes on the decode boundary:** *accept* (a rule is
  emitted), *ignore* (silently, or with a stderr warning when live data is
  dropped), *reject* (`ValueError` before a `Puzzle` exists, or
  `MalformedPuzzleError` later from `verdict`).
- **Glossary caveat.** The CONTEXT.md glossary update (issue **#330**) is still
  open, so its prose lags the code in at least one decoder-facing spot — it
  still calls a doubler "a color-marked cell in a SudokuMaker link"
  (`CONTEXT.md:373`), the retired channel. Treat the decoder as authoritative;
  the recognized-name naming (`Doubler` / `S-cell` / `Schrödinger` / `Sum` /
  `Killer`) may still be renamed by #330 — see "Naming risks" at the end.

---

## 1. Board size and digit domain — the envelope every constraint rides in

Read before the per-constraint tables: size and domain gate whether a link
decodes at all, and every address below is computed from the size.

**Size** (`_board_size`, `sudokumaker.py:322-350`), most specific first:

1. `width` present → `cols = width`; `rows = height` if present, else
   `len(cells) // width`.
2. else `size` present → square `size × size`.
3. else → the classic default **9** (SudokuMaker omits the header only on the
   default 9×9, ADR-0011; `sudokumaker.py:87-89`, `sudokumaker.py:342-343`).

Then two hard checks: the shape must be square (`rows == cols`, else
`ValueError` "non-square link", `sudokumaker.py:344-346`) and the cell count
must match (`rows*cols == len(cells)`, else `ValueError` "cells do not match
size", `sudokumaker.py:347-349`). `width`/`size`/`height` must be plain ints —
a `bool` is refused (`_as_int`, `sudokumaker.py:353-359`). A non-`list` `cells`
is refused up front (`sudokumaker.py:331-334`).

**Domain** (`_digit_domain`, `sudokumaker.py:362-373`): `minDigit..maxDigit`
when present, else `1..N`. `maxDigit` defaults to `minDigit + size - 1`, and the
span is validated: `maxDigit - minDigit + 1 == N` or `ValueError` "domain … is
not N digits". A classic link omits both → `1..9`.

**Under an S-cell marker the domain widens** (`_schrodinger_domain`,
`sudokumaker.py:376-382`): `range(minDigit, minDigit + size + 1)` — one extra
digit (the classic `k = 1`), `minDigit` defaulting to 1, `maxDigit` ignored.
This is what makes a `minDigit:0` 6×6 (domain `{0..6}`, 7 values on a 6-wide
board) decode instead of being rejected by the classic span check
(`sudokumaker.py:260-265`).

**Supported sizes.** The decoder is size-agnostic (any square N), and the
fixtures exercise **4×4, 6×6, 9×9** (`src/gridfind/links/`): `found-classic-4x4`
(`size:4`), `found-classic-6x6` (`size:6`), `found-classic-9x9` (headers absent
→ 9), plus `found-jigsaw-6x6`, `found-schrodinger-6x6` (`width:6/height:6`),
`found-xv-9x9`. Box geometry exists for exactly these three N (`BOX_SHAPE`,
`layers/regions.py:64`).

---

## 2. Cell-level state — givens vs. placements vs. pencilmarks

How the *state-under-test* is read per cell (`_decode_cell`,
`sudokumaker.py:416-444`). Cell index `i` → address `R{i//N+1}C{i%N+1}`
(`_address`, `sudokumaker.py:647-651`).

| SudokuMaker cell | gridfind directive | Source |
|---|---|---|
| `{given:true, value:v}` | `Given(address, v)` — a setter clue on the `Puzzle` | `sudokumaker.py:437-439` |
| `{value:v}` (no `given`) | `Placement(address, v)` — a solver placement in `WorkingState` | `sudokumaker.py:440` |
| `{candidates:mask}` | `Candidate(address, digits)` — center pencilmarks; `digits = {d in domain : mask & (1<<d)}` | `sudokumaker.py:441-443` |
| `{colors:…}`, `{cornerPencilMarks:…}`, `{}` | ignored — empty `_CellDecode` | `sudokumaker.py:444` |

`candidates` is a bitmask, bit `d` = digit `d` (`2^d`); only digits *in the
current domain* survive the mask (`sudokumaker.py:442`). `cornerPencilMarks` and
`colors` have no gridfind equivalent and are dropped
(`sudoku-link-formats.md` §4a).

**S-cell cells read their center marks instead** (`_s_cell_from_marks`,
`sudokumaker.py:447-461`), reached only for an address in an S-cell marker cage
(§6). The mark *count* picks the directive:

| Center marks | Directive | Meaning | Source |
|---|---|---|---|
| exactly **2** | `SCellPin(address, {a,b})` | S-cell pinned to that digit pair | `sudokumaker.py:455-456` |
| exactly **1** | `HalfSCell(address, d)` | S-cell known to contain `d`, partner free | `sudokumaker.py:457-459` |
| **0 or ≥3** | `BareSCell(address)` — stray marks (if any) ride along as a `Candidate` | S-cell, digits free | `sudokumaker.py:460-461` |

A settled `value` on an S-cell-marked cell is the is-S-vs-settled contradiction:
`ValueError` "S-cell … also holds a value" (`sudokumaker.py:432-435`).

**Verdict-path trap (unchanged from §4c of the format doc).** S-cell directives
live on `WorkingState.s_directives`, not on the `Puzzle` (ADR-0006). The verdict
call must thread the working state — `verdict(puzzle, working_state)` — or every
S-cell directive is silently dropped.

---

## 3. The constraint table — size-independent unless noted

Each constraint's four columns: **(a)** setter action, **(b)** wire shape,
**(c)** decode result, **(d)** accept/ignore/reject boundary. Every wire type is
one row of `DECODER_REGISTRY` (`sudokumaker.py:859-884`); rows/cols are always
emitted unconditionally (`sudokumaker.py:285`).

### 3.1 Classic (rows / columns / boxes)

- **(a)** Default sudoku ruleset — the setter builds a normal grid; boxes come
  from the "Regions" / sudoku ruleset.
- **(b)** `type 0` (no params, the sudoku ruleset) + `type 1`
  `{regions:[…N² ids…]}` (the box tiling as a flat row-major region-id array).
  Confirmed: `found-classic-4x4` carries `type 0` + `type 1`.
- **(c)** `rows-distinct` + `cols-distinct` are emitted unconditionally
  (`sudokumaker.py:285`); rows/cols are *never* explicit on the wire (`type 0`
  implies them). The `type 1` matrix: if it equals the board's box tiling
  (`_classic_regions_for`, `sudokumaker.py:496-504`) → bare
  `Constraint("regions-distinct")`; otherwise → jigsaw (§3.2)
  (`_regions_constraints`, `sudokumaker.py:464-485`).
- **(d)** *Accept* always. A **missing** `type 1` means the setter asked for no
  regions — a Latin square, rows+cols only, no boxes invented
  (`sudokumaker.py:16-23`, `sudokumaker.py:481-482`). Box-equality is only
  testable for N ∈ {4,6,9} (`size in BOX_SHAPE`, `sudokumaker.py:483`); on any
  other N the matrix always rides as explicit params.

### 3.2 Jigsaw (irregular regions-distinct)

- **(a)** Draw custom regions (non-box region shapes) in SudokuMaker's regions
  tool. *(UI gesture not further determinable from repo sources.)*
- **(b)** `type 1` `{regions:[…N² ids…]}` — same block as the box case, but the
  id array is *not* the standard box tiling. Confirmed: `found-jigsaw-6x6`
  carries `regions:[4,4,1,1,1,1,4,4,…]` (an irregular partition).
- **(c)** `Constraint("regions-distinct", params={"regions": matrix})` — the
  matrix rides onto `params["regions"]` verbatim, **unvalidated**
  (`sudokumaker.py:484-485`).
- **(d)** *Accept* (decode never validates the matrix). A malformed partition
  surfaces later as `MalformedPuzzleError` from `verdict`, not from decode
  (`sudokumaker.py:20-23`, `sudokumaker.py:476-479`). A `disabled` `type 1` is
  skipped — a link may carry a disabled duplicate alongside the live one
  (`_enabled_blocks`, `sudokumaker.py:490-493`, `sudokumaker.py:507-527`).

### 3.3 Thermometer

- **(a)** Draw a thermo line (bulb + stem). SudokuMaker's "slow" toggle sets the
  non-strict variant.
- **(b)** `type 300` `{slow: bool, thermometers: [[cell indices, ordered, bulb
  first], …]}`. Confirmed: `found-thermo-4x4` carries two `type 300` blocks, one
  `slow:false`, one `slow:true`.
- **(c)** One `Constraint("thermo", params={"path": addresses, "slow": slow})`
  per path; indices map row-major to addresses, **order preserved (bulb first)**;
  `slow` rides onto every path in the block; the cosmetic `style` object is
  ignored (`_thermo_constraints`, `sudokumaker.py:817-833`). The strict/non-strict
  split is the `thermo` layer's concern, not the decoder's
  (`sudokumaker.py:163-168`).
- **(d)** *Accept*. `disabled` block skipped; empty `thermometers` adds nothing
  (`sudokumaker.py:826-829`).

### 3.4 White kropki (difference dot)

- **(a)** Place a white dot on the edge between two orthogonally-adjacent cells.
- **(b)** `type 200` `{clues:[{value, edge}], negative:[…]}`. `value` is the
  target difference; `edge` is an integer naming the cell pair. Confirmed:
  `found-kropki-4x4` → `clues:[{value:1, edge:…}]`.
- **(c)** One `Constraint("pair-difference", params={"cells":[a,b],
  "diff": value})` per clue; `edge` → adjacent pair via `_edge_to_pair`; `value`
  is passed **verbatim** as `diff` — a labelled non-1 dot is honored at its
  value, never coerced to the consecutive default (`_kropki_constraints`,
  `sudokumaker.py:117-122`, `sudokumaker.py:618-628`).
- **(d)** *Accept* the positive clues. A non-empty `negative` list is
  **warn-and-dropped to stderr** — the verdict is computed without the negative
  rule (`_warn_dropped_negative`, `sudokumaker.py:530-540`,
  `sudokumaker.py:595`). An `edge` naming no in-bounds pair on the board →
  `ValueError` (`_edge_to_pair`, `sudokumaker.py:561-571`). `disabled` block
  skipped.

### 3.5 Black kropki (ratio dot)

- **(a)** Place a black dot on the edge between two orthogonally-adjacent cells.
- **(b)** `type 201` — same wire shape as white kropki (`{clues:[{value, edge}],
  negative:[…]}`). The type number *is* the white/black discriminator
  (`sudokumaker.py:117-129`). Confirmed: `found-black-kropki-4x4` →
  `type 201, clues:[{value:…}]`.
- **(c)** One `Constraint("pair-ratio", params={"cells":[a,b], "k": k})` per
  clue; `value` read as the target integer ratio `k`, honored verbatim — a
  labelled non-2 dot is never coerced to 2 (`_black_kropki_constraints`,
  `sudokumaker.py:631-644`).
- **(d)** *Accept* positive clues; `negative` warn-and-dropped as white. A
  **non-integer** `value` → `ValueError` at decode (`_as_int`,
  `sudokumaker.py:641`) — modeling a wrong verdict would be worse than refusing.
  Out-of-range `edge` → `ValueError`. `disabled` skipped.

### 3.6 XV

- **(a)** Place an X (=10) or V (=5) clue on the edge between two
  orthogonally-adjacent cells.
- **(b)** `type 202` `{clues:[{value, edge}], negative:[…]}` — same wire shape
  as kropki. `value` is 10 (X) or 5 (V). Confirmed: `found-xv-9x9` →
  `clues:[{value:10, edge:70}, {value:5, edge:103}]`.
- **(c)** One aliased group-sum `Constraint` per clue: `value` selects the
  existing `x`/`v` group-sum alias from `ALIAS_REGISTRY` (10→X, 5→V), emitted as
  `Constraint(alias, params={"cells":[a,b]})` (`_xv_constraints`,
  `sudokumaker.py:103-115`, `sudokumaker.py:599-615`).
- **(d)** *Accept* clues whose `value` is 10 or 5. **Any other `value` →
  `ValueError`** "neither X (10) nor V (5)" (`sudokumaker.py:608-612`).
  `negative` warn-and-dropped; out-of-range `edge` → `ValueError`; `disabled`
  skipped.

### 3.7 Killer cage (`type 301`)

- **(a)** Draw a killer cage with SudokuMaker's killer-cage tool; optionally type
  a cage sum.
- **(b)** `type 301` `{cages:[{cells, value}]}`; `cells` is a row-major index
  list, `value` the killer sum (a JSON number). Confirmed: `found-cage-4x4` →
  `cages:[{cells:[1,2], value:5}]`.
- **(c)** Each cage → a no-repeats `Constraint("cage", params={"cells":…})`; a
  **positive** `value` additionally emits `Constraint("group-sum",
  params={"cells":…, "sum": value})` over the same cells (spec #240;
  `_killer_cage`, `sudokumaker.py:660-669`; `_cage_constraints`,
  `sudokumaker.py:672-686`).
- **(d)** *Accept*. `value` **0 or absent** = SudokuMaker's own no-sum cage →
  `cage` alone, no `group-sum` (`sudokumaker.py:136`, `sudokumaker.py:666`).
  `disabled` block skipped; empty `cages` adds nothing. (SudokuMaker's
  killer-cage tool refuses to store an out-of-range sum, e.g. a doubled cage
  over 45 — that sum reaches gridfind only through a cosmetic cage, §3.8 /
  ADR-0008.)

### 3.8 Cosmetic cage (`type 2001`) — and the doubler / S-cell markers

`type 2001` is SudokuMaker's *decoration* tool (a named/colored cage), not the
killer-cage tool (ADR-0008). Its wire shape is identical to `type 301` —
`{cages:[{value, cells}], name?, style?}` — but `value` is a **string** and a
top-level `name` may mark the block as a variant declaration. The `name`
classifies the whole block (`markers.cosmetic_cage_kind`):

**Recognized-name set:** the name → shape registry, `sudokumaker.naming`
(`_NAME_REGISTRY`), built in #434 and read by `markers.cosmetic_cage_kind`.

| `name` (normalized) | Kind | Source |
|---|---|---|
| absent / blank | `unnamed` (no rule — warn-drop) | `naming.py` / `markers.cosmetic_cage_kind` |
| `sum`, `killer` | `killer` (real cage, name discarded) | `naming._NAME_REGISTRY` |
| `doubler` | `doubler` (position marker) | `naming._NAME_REGISTRY` |
| `s-cell`, `schrödinger`, `schrodinger` | `s-cell` (position marker) | `naming._NAME_REGISTRY` |
| anything else | `unrecognized` (no rule — warn-drop) | `markers.cosmetic_cage_kind` |

**Matching rule:** the `name` is `.strip()`-trimmed and `.lower()`-cased before
lookup — **case-insensitive and whitespace-trimmed**
(`naming._normalize_component_name`). A non-string or blank `name` is
`unnamed`. Both the umlaut `schrödinger` and the ASCII fold `schrodinger` are
recognized (a link may carry either).

#### 3.8a Killer cage (`name: Sum` / `Killer`)

- **(a)** Draw a decorative/named cage; type a numeric label for a sum.
- **(b)** `type 2001` `{cages:[{value:str, cells}]}`, `name` `Sum`/`Killer`.
  Confirmed shape: `found-doubler`'s sum sibling carries
  `{'value':'9','cells':[8,12]}`.
- **(c)** Decodes exactly as a killer cage: each cage → no-repeats `cage`; a
  **numeric non-zero string** `value` graduates to a `group-sum`
  (`cages._cosmetic_cage_killer_sum` parses `int(value)`, returns `None` for
  non-numeric/blank). This is the *only* channel an out-of-range cage sum (a
  doubler inside a cage) reaches gridfind through (ADR-0008 decision 3).
- **(d)** *Accept*. A sumless / non-numeric label still emits its `cage` — the
  sum-parse gates only the `group-sum`, not liveness. `disabled` skipped;
  empty `cages` adds nothing.

#### 3.8a′ Unnamed cosmetic cage — no rule (ADR-0012, #435)

- An absent/blank `name` carries no rule at all: a non-empty block is
  warn-and-dropped to stderr, naming it (`cages._warn_dropped_cosmetic_cage`);
  an empty one is silently skipped like any other empty block. Before #435 this
  block decoded as an ordinary killer cage — the same reading as a named
  `Sum`/`Killer` cage — which meant a purely decorative box a setter drew
  silently became a load-bearing rule.

#### 3.8b Doubler marker (`name: Doubler`)

- **(a)** Draw a cosmetic cage over the doubler cells and name it `Doubler`.
- **(b)** `type 2001`, `name:"Doubler"`, `cages:[{cells:…}]`. Confirmed:
  `found-doubler-4x4` carries `type 2001` with 2 cages.
- **(c)** One `ModifierDirective(address, is_modifier=True)` per contained cell
  and **no** `cage`/`group-sum` for that block — the `cages` supply the cell
  list, not a killer rule (`sudokumaker.py:783-790`). When any doubler directive
  is produced, `decode_link` appends `Constraint("doubler")`
  (`sudokumaker.py:297-298`). Marking is orthogonal to the cell's digit — a
  given/placement on a marked cell still decodes normally
  (`sudokumaker.py:238-242`, `sudokumaker.py:429-431`).
- **(d)** *Accept*. `ModifierDirective`s ride on `WorkingState.modifier_directives`
  (`sudokumaker.py:301-306`). `disabled` skipped.

#### 3.8c S-cell marker (`name: S-cell` / `Schrödinger` / `Schrodinger`)

- **(a)** Draw a cosmetic cage over the S-cells and name it `S-cell` (or
  `Schrödinger`/`Schrodinger`).
- **(b)** `type 2001`, `name` in the S-cell set, `cages:[{cells:…}]`.
- **(c)** Presence of any such block **infers Schrödinger-ness on its own**
  (`sudokumaker.py:32-37`, `sudokumaker.py:254-260`): its cell addresses are
  gathered (`_scell_marker_addresses`, `sudokumaker.py:799-814`), the domain
  widens by the derived `k = 1` digit (§1), the `schrodinger` constraint is
  synthesized (`sudokumaker.py:295-296`), and each contained cell routes through
  the S-cell per-cell branch (§2) reading its center marks. The `type 2001`
  block itself emits **no** `cage`/`group-sum` (`sudokumaker.py:780-781`).
- **(d)** *Accept*. A settled `value` on a marked cell → `ValueError` (§2,
  `sudokumaker.py:432-435`). `disabled` block contributes nothing — neither the
  address set nor the domain widening (`sudokumaker.py:807-814`).

#### 3.8d Unrecognized cosmetic-cage name

- **(d)** No rule — the same warn-drop as an unnamed block (§3.8a′), naming the
  unrecognized name (`cages._warn_dropped_cosmetic_cage`). Before #435 this
  raised `ValueError`, downgradable to strip-and-honor via the now-retired
  `ignore_unknown_named_cages` (spec #324, ADR-0012).

### 3.9 Global toggles — anti-knight, anti-king, the two diagonals

Four board-wide rules SudokuMaker carries as bare `{type: N}` blocks — no
payload, the enabled presence is the whole rule. The wire types were read off
setter-supplied links, never guessed.

- **(a)** Enable the toggle in SudokuMaker's global-constraints panel (exact
  UI gesture unconfirmed against the live app — see the setter guide's
  provisional flags).
- **(b)** A bare block, one per rule: `type 13` anti-knight, `type 12`
  anti-king, `type 10` negative diagonal (`\`), `type 11` positive diagonal
  (`/`). The two diagonals also carry a cosmetic `style` (color, thickness)
  gridfind ignores. The diagonals are **independent** switches — a link may
  carry one, the other, or both (both together is X-sudoku).
- **(c)** One `Constraint` per enabled block: `anti-knight`, `anti-king`,
  `negative-diagonal` (`\`), `positive-diagonal` (`/`). Each diagonal decodes to
  its own single-diagonal constraint rather than the both-diagonals `diagonal`,
  so a lone toggle constrains only the diagonal the setter enabled
  (`_global_toggle_handler`). A cosmetic `style` on the block is ignored.
- **(d)** *Accept* an enabled block. A `disabled` block is skipped.

---

## 4. Accept / ignore / reject — the boundary rules, consolidated

Three distinct outcomes; keep them separate.

**Ignore silently — `disabled` blocks.** Every per-type decoder iterates through
`_enabled_blocks`, which skips any block with `disabled: true`
(`sudokumaker.py:507-527`). The setter switched it off, so it is not part of the
puzzle even for a type gridfind decodes — no warning
(`sudokumaker.py:894-916`, `sudokumaker.py:922-924`). A real link may carry a
disabled duplicate alongside the live one.

**Ignore with a stderr warning — unmodeled types carrying live data.**
`_warn_on_dropped_constraints` (`sudokumaker.py:894-935`) walks every enabled
constraint whose `type` is *not* in `DECODER_REGISTRY`. If it carries live data
(`has_live_data`: a non-empty `clues`/`negative`/`cages` list, or an
`input.groups` group with real cells; `sudokumaker.py:938-967`) it is dropped
**loudly** — `warning: ignoring unmodeled constraint '<name>' (type N) — verdict
computed without it`, named by `definition.name` when present
(`constraint_name`, `sudokumaker.py:970-980`). An inert unmodeled block
(empty/cosmetic-only payload) is dropped **quietly**. The `type 2003`
Schrödinger marker block ships an empty payload, so it is always inert and
dropped silently (`sudoku-link-formats.md` §4c; confirmed: `found-schrodinger-6x6`
carries `{type:2003}`).

**Ignore with a stderr warning — a decoded type's `negative` list.** Kropki/XV
positive clues decode, but a non-empty `negative` list is warn-and-dropped from
the type's own decoder (`_warn_dropped_negative`, `sudokumaker.py:530-540`,
`sudokumaker.py:595`).

**Reject as an unsupported link — `ValueError` before any `Puzzle` exists.**
Deliberately kept as `ValueError`, not `MalformedPuzzleError`: this is the
decoder finding a link it does not support (`sudokumaker.py:41-49`). The paths:

| Cause | Message stem | Source |
|---|---|---|
| non-list `cells` | "puzzle carries no cells array" | `sudokumaker.py:331-334` |
| non-square shape | "non-square link: RxC" | `sudokumaker.py:344-346` |
| cell-count ≠ size² | "cells do not match size" | `sudokumaker.py:347-349` |
| non-int header (incl. `bool`) | "width/size/… must be an int" | `sudokumaker.py:353-359` |
| domain span ≠ N (non-Schrödinger) | "domain … is not N digits" | `sudokumaker.py:370-372` |
| XV `value` ∉ {10,5} | "neither X (10) nor V (5)" | `sudokumaker.py:608-612` |
| black-kropki `value` non-integer | "black-kropki value must be an int" | `sudokumaker.py:641`, `353-359` |
| edge names no valid pair | "edge … does not name a valid cell pair" | `sudokumaker.py:567-571` |
| S-cell-marked cell holds a value | "S-cell … also holds a value" | `sudokumaker.py:432-435` |

**Reject as a malformed puzzle — `MalformedPuzzleError` from `verdict`.** A
`Puzzle` `decode_link` produces is never itself malformed; a malformed jigsaw
matrix, an undeclared digit, a domain the placements violate, etc. surface later
from `verdict`, not from decode (`sudokumaker.py:41-49`, `sudokumaker.py:20-23`).
The distinction is worth keeping: only a `ValueError` means the *link* is bad,
not the puzzle.

---

## 5. Naming risks — CONTEXT.md glossary (#330 still open)

Flagged per the caveat: the decoder is authoritative; these glossary spots may
still be reworded by #330, and the recognized-name tokens themselves could be
renamed.

- **`CONTEXT.md:373`** still describes a modifier's declared position as "a
  color-marked cell in a SudokuMaker link, ADR-0008" — the **retired** red-bit
  channel. Post-#328 the declaration channel is a named `Doubler` cosmetic cage
  (`sudokumaker.py:783-790`). This is a decoder-facing staleness #330 should fix.
- **`CONTEXT.md:325-327` / `349-352`** still say the killer sum is "S-blind" and
  that `group-sum` "raises not-Schrödinger-ready yet" over a named S-cell.
  ADR-0010's consequences note this was already stale — issue #235 retired that
  refusal and `group-sum` reads `s_value` through `value_expr` today
  (`0010-doubled-schrodinger-cell-value.md:92-95`). Engine-internal, not
  decoder-facing, but the same #330 pass should catch it.
- **Recognized-name tokens** (`Doubler`, `S-cell`/`Schrödinger`/`Schrodinger`,
  `Sum`/`Killer`) are the literal strings the decoder matches
  (`sudokumaker.py:150-161`). If #330 renames the marker vocabulary, both the
  decoder constants and this guide move together — treat the strings above as
  current-as-of-code, not permanently frozen.

**Not determinable from repo sources:** the precise SudokuMaker UI gestures for
drawing a *jigsaw region* and for *naming a cosmetic cage* (§3.2, §3.8) — the
repo confirms the wire result but not the exact click-path in the app. Flagged
rather than invented.
