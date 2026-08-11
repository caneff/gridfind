# gridfind — Context glossary

Canonical vocabulary for gridfind: general grid-puzzle constraint solving and
validation on **CP-SAT (OR-Tools)**. Given a partly-built puzzle, decide
**found / broke / unknown**.

Glossary only — no implementation detail. Decisions live in the wayfinder map
([#1](https://github.com/caneff/gridfind/issues/1)); this file names the terms
those decisions settled. Cross-references like _(map #1, decision N)_ point at
the deciding record, not a restatement.

The vocabulary is engine-neutral by design (map #1, decision 13): a term never
says "CP-SAT variable" or "CP-SAT constraint" where a domain word will do.

---

## Verdicts

The whole point of gridfind: classify a **well-formed** working state as one of
three (map #1, decision 15). The core runs **pure-satisfaction** search — it
races a broke-proof against a witness-find, never an objective solve.

- **found** — a **witness** exists; here it is. The first solution CP-SAT
  returns, with no enumeration and no uniqueness claim.
- **broke** — proven that **no** completion exists (the space is infeasible).
  A change that merely lands on a _different_ valid grid is not broke — that is a
  different valid puzzle. Broke is a consistency claim: does any completion
  exist, never whether one intended solution survived.
- **unknown** — neither decided within the search budget. Carries **no**
  near-miss and no rank-error (both dropped with the objective solve; map #1, out
  of scope).

- **malformed** — an input gridfind refuses *before* it classifies: a given,
  placement, or candidate naming a digit the board never declared, or an alias
  fixing a parameter the constraint also states. Raised as `MalformedPuzzleError`,
  never returned — a malformed puzzle never reaches a verdict. Not a fourth
  answer: **broke** is a consistency claim ("no completion exists"), and "you
  wrote it wrong" is not that
  ([#101](https://github.com/caneff/gridfind/issues/101),
  [#102](https://github.com/caneff/gridfind/issues/102),
  [#107](https://github.com/caneff/gridfind/issues/107)).

- **witness** — a concrete full grid satisfying every rule in the stack. The
  proof object returned by **found** — a usable grid, not just a yes.

- **result** — what asking for a verdict hands back: the verdict itself, plus
  the **witness** when the verdict is **found**. The verdict is the word; the
  result is the thing carrying it. Two terms because one object holds both — a
  result is not a fourth verdict.

---

## Cells and content

- **cell** — the atom (map #1, decision 2). You think in cells; the solver fills
  their content. Two kinds:
  - **grid cell** — a cell that obeys the active variant's grid rules and sits
    inside the grid.
  - **outside cell** — a cell off the grid (an arrow target, a room member) that
    obeys **no** grid rule and participates only through the clues that name it.

- **content** — a cell's ordered sequence of one or more plain integer variables
  (a bool is just a 0/1 integer). Length 1 for an ordinary cell; length 2 for a
  Schrödinger **S-cell** (map #1, decisions 3–4). "Variable" is an implementation
  word — kept out of the spoken vocabulary. Domains are plain integer only; a
  layer may add a one-hot channel locally for one rule if it wants.

- **pair** — two cells named together as one clue's subject. Nothing more: the
  two cells need not be adjacent, aligned, or even on the grid. The smallest
  grouping a two-cell rule addresses.

- **domino** — a pair whose two cells are orthogonally adjacent. Every domino is
  a pair; a pair is a domino only when its cells touch. gridfind enforces
  adjacency for no rule yet (issue #43) — until then a rule that wants a domino
  is handed an explicit **pair** and trusts the setter that it is one.

---

## Composition model

Four words name four levels, told apart by how many of each there are: one
**variant** is stated as many **constraints**, each emitting many **rules**, all
handled by one **layer**.

- **variant** — a rule family: XV, killer, thermo, Schrödinger. What a setter
  names when they say what kind of puzzle this is. One variant is served by one
  layer.

- **constraint** — one typed statement in a puzzle: a killer cage with its cells
  and its sum, an X clue naming its pair, or a bare `sudoku` naming a family that
  carries no data of its own. The level a setter writes and gridfind serializes.
  Many constraints per variant — two X clues are two constraints of one variant.

- **rule** — one atomic relation a layer emits over cell content (an AllDifferent,
  a sum, an equality). Many rules per constraint. _Constraint_ is retired at
  **this** level and stays retired (map #1, decision 6): the solver's internal
  constraint hides behind _rule_. The word is spoken only one level up, where
  nothing can collide with it — a killer cage is not one rule, it becomes
  several.

- **layer** — a composable, parameterized rule-family module (map #1, decisions
  5, 7). Layers are granular, not monolithic puzzle types: `board`,
  `rows-distinct`, `cols-distinct`, `regions-distinct(region-map)`,
  `line-count-distinct`, and so on. Classic sudoku is
  `board + rows-distinct + cols-distinct + regions-distinct(3×3)`; drop the
  regions layer and it is a Latin square. A layer contributes cells and rules and
  knows no puzzle concepts beyond its own.

- **layer kind** — a parameterized layer before its parameter is supplied. One
  kind serves several layers: fix a partition on the distinct-over-groups kind
  and you get `rows-distinct`, `cols-distinct`, `regions-distinct`. A layer
  answers to a registered name; a kind answers to none, and is named for the
  rule shape it emits. Most layers are their own kind — the word is only needed
  where one kind serves many.

- **solver constraint** — one constraint handed to the solver, a level below
  _rule_ and named only where that distance matters (issue #82). A rule is not
  one solver constraint: `emit_distinct_count` spends O(cells × digits) of them
  on a single counting rule, over 160 for a 9-cell row. The term names no
  vendor, which is what decision 13 protects — say _solver constraint_, never
  "CP-SAT constraint".

- **board** — the layer that registers grid cells and arranges them (map #1,
  decisions 7, 14). The core holds zero geometry; a `board` layer supplies it —
  `RxCy` addressing for a rectangular grid, a different board layer for hex or
  graph. `board` registers cells and emits no rules of its own.

- **structure registry** — the channel through which layers talk to each other
  (map #1, decision 9). Layers reference each other's named **structures**, never
  each other directly. A cell exposes its content as a named structure; a
  variable-width window falls out of concatenating cells' content, blind to
  whether any cell is an S-cell. Registry wiring is build-time only, so
  composition costs nothing at solve time — a composed plain sudoku emits the
  identical CP-SAT model a hand-written solver would.

- **carried field** — setter input riding on the engine for layers to read
  (`constraints` and `board`; two-channel rule in
  [ADR-0004](docs/adr/0004-binding-not-provenance.md)). The line between the two
  channels is _must the producer and the consumer stay apart_: the registry
  carries facts that need late binding, a carried field carries what is fixed
  before any layer runs. Setter input needs its own channel because `verdict`
  and `emit_distinct_count` consume it and neither is a layer.

- **cell geometry** — the descriptor of the puzzle's cell space: the board size,
  the digit values, the box tiling, and the grid of `RxCy` addresses
  ([ADR-0004](docs/adr/0004-binding-not-provenance.md)). Metadata only — it holds
  no **content** and no solver state. It is built from the setter's board before
  any layer runs, so anyone may read it: layers off the engine, `sudokumaker` from
  the board directly. Adjacency joins it when the first adjacency variant lands.
  Named for the cell space it describes, not for any one **cell**. _Decided in
  ADR-0004 but not yet built — today `board` still owns the geometry and registers
  the `grid` addresses through the structure registry; this entry names the target,
  not the current code._

- **two-phase build** — the build protocol that makes composition
  order-insensitive (map #1, decision 10; engine↔layer contract frozen in
  [ADR-0001](docs/adr/0001-engine-layer-contract.md)). **Phase 1**: every layer registers its
  cells and structures (a Schrödinger layer widens grid-cell content to length 2
  here). **Phase 2**: every layer emits its rules against the now-final structures
  (a quad-rank layer concatenates the settled content here).

- **layer dependency** — a validity check a layer declares, not a build-order
  crutch (map #1, decision 10): e.g. a quad-rank layer declares it needs a board
  with grid cells. Missing dependency → the build refuses.

- **bridge layer** — the composition fallback for a pair of layers that cannot
  reconcile through cell content alone (map #1, decision 11). A named per-pairing
  layer that declares the pair it bridges and may reference **both** layers'
  structures. The engine auto-applies it when both layers are in the stack
  (invisible in the header). If a pair needs glue and no bridge is registered, the
  engine **refuses rather than guesses**. A header names a bridge explicitly only
  when a pair has more than one possible reconciliation.

- **preset** — a named, reusable bundle of layers (map #1, decisions 7–8), e.g.
  `classic-sudoku`. A header may list presets; each expands to its constituent
  layers. A puzzle is, ultimately, a **stack of layers**. A `sudoku` constraint
  is a preset: it expands to the three basic distinct rules.

- **alias** — a second spelling of one constraint type, expanding to the
  canonical type with a param already fixed: an **X clue** is a `pair-sum` of
  10. A preset makes many constraints out of one; an alias makes one out of
  one. Both expand at load, before any layer sees them.

---

## Working state

The shared-core half of the working-state grammar (map #1, decision 12) — the
directives every grid puzzle understands. Each active layer registers its own
directives on top; a header line declares the active layer stack.

- **working state** — the setter's in-progress hand-solve fed to gridfind: some
  cells placed, others narrowed. The question asked of it is always a verdict —
  "have I broken it yet?"

- **given** — a grid cell the setter has placed to a single digit. Content pinned
  to one value. Stays literal under the Schrödinger layer: it fixes the cell's
  base slot, so the given digit is the cell's value, or the lower digit if the
  cell turns out to be an **S-cell**. It never becomes a **bare placement** —
  that refinement is the hand-solve **placement**'s alone (see below).

- **candidate / pencilmark** — a cell narrowed to a subset of digits (e.g.
  `{2,5,7}`) without being placed. Weaker information than a given.

- **placement** — asserting a digit sits at a cell (`RxCy`) as part of the
  hand-solve. The core-level place directive; layers may refine what a placement
  means for their own cells. Under the Schrödinger layer it refines to a
  **bare placement**: the digit sits in the cell's content, in *either* slot, so
  placing a digit that a solve later reveals as an **S-cell**'s upper half does
  not break. That is where placement and **given** deliberately diverge — a
  given stays literal to the base slot, a placement loosens to the whole content
  (map #1, decision 12; #142).

---

## `pair-sum` layer

The first real data-bearing variant (issue #66), and the pattern later variants
copy. A clue names a **pair** and a target; the layer sums the pair's content to
it, one rule per clue. Explicit-pair and positive-only — it sums the named pair
without asking whether it is a **domino**, and constrains only marked pairs (the
negative rule against *unmarked* adjacent pairs is out of scope).

- **pair-sum** — the constraint and the rule it emits:
  `{type: pair-sum, cells: [a, b], sum}`. The canonical form every XV clue
  expands to.
- **XV** — the setter-facing variant, two **aliases** of a pair-sum whose
  target is named rather than written: an **X clue** is a pair-sum of 10, a
  **V clue** a pair-sum of 5.

---

## `pair-difference` layer

The second explicit-pair variant (issue #129, spec #127), landing beside the
`emit_over_pairs` extraction (#42 decision 5, #128) that lets it and `pair-sum`
share one emit pattern. A clue names a **pair** and a target `k`; the layer
constrains the pair's content to differ, in absolute value, by exactly `k`,
one rule per clue. Explicit-pair, positive-only, and absolute — like pair-sum
it never asks whether the pair is a **domino** and constrains only marked
pairs, and either cell may hold the larger value (no directed `a - b = k`
form). No setter-facing alias in this change; kropki-white / consecutive
(`k = 1`) can alias later.

- **pair-difference** — the constraint and the rule it emits:
  `{type: pair-difference, cells: [a, b], diff: k}`.

---

## `schrodinger` layer

Terms carried over from quad-rank's Schrödinger variant, re-rooted onto the
layer model. This layer widens selected grid cells to length-2 content in phase 1
and owns the working-state directives below.

- **S-cell** — a grid cell whose content is length 2: it holds an unordered pair
  of digits rather than one. In the Schrödinger sudoku a permutation of cells (one
  per row, one per column) are S-cells, so every row and column holds all ten
  digits `0–9` exactly once; which cells are S-cells is discovered by solving, not
  given.

The Schrödinger working state spans two independent axes — **S-cell-ness** (is
this position a singleton, an S-cell, or unknown?) and **digit-content** — so its
directives name a point on each:

- **singleton pin** — asserts a cell is a **singleton** (not an S-cell) holding
  digit `d`. The Schrödinger analog of a **given**, carrying the extra
  "not an S-cell" claim that a bare placed digit lacks.
- **S-cell pin** — asserts a cell **is** an S-cell holding the pair `{a,b}`.
  Collapses both axes.
- **bare placement** — asserts `d ∈ content(cell)` without resolving S-status: the
  cell is a singleton `d` or an S-cell holding `d` alongside an unknown partner.
  The loosest directive — fixes a digit, leaves S-cell-ness free.
- **bare singleton** — asserts a cell **is a singleton** without saying which
  digit. A singleton pin minus its digit.
- **bare S-cell** — asserts a cell **is an S-cell** without saying either digit. An
  S-cell pin minus its pair.
- **half S-cell** — asserts a cell **is an S-cell** and that digit `d` is one of
  its two digits, partner unknown. Between an S-cell pin and a bare S-cell;
  equivalently a bare placement whose S-cell-ness is pinned true.

Three ways a Schrödinger directive is **malformed** (refused before classify,
never a verdict; #142): a digit-bearing directive naming a digit outside the
board's values — the same rule that already governs a **given** or
**candidate**; an **S-cell pin** whose pair is not exactly two distinct digits,
counted after the pair collapses duplicates, since one digit is no pair and
three cannot be one; and *any* of these directives riding a layer stack that has
no `schrodinger` layer, since no S-axis exists to honor. A directive whose digits
are all legal but whose claim no completion can satisfy is not malformed — it is
**broke**, the ordinary infeasibility the solver reports.

The line holds only for *content* errors — a bad digit, a mis-sized pair, a
missing layer. A structurally broken save (an unknown directive `kind`, a missing
key) is ordinary broken JSON, not a `MalformedPuzzleError`: malformed is a claim
about what the puzzle says, not about whether the file parses.

---

## `cage` layer

The no-repeats-only sibling of a region (issue #157, spec #156 decision
#150): a clue names a set of cells and the layer forbids a digit repeat among
them, adding no cover pressure. Structured like `pair-sum` (a clue-looping
layer pulling every `cage` constraint via the dispatch), not like the
partition-driven `regions-distinct` — no shared base with it. Unlike a
region, a cage need not use every domain digit: a 7-cell cage on a 9-digit
board is legal. On a Schrödinger-widened board the no-repeats rule reaches
both of an S-cell's digits, but states no target digit count, so a cage never
forces a cell to become an S-cell.

- **cage** — the constraint and the rule it emits: `{type: cage, cells:
  [...], name?}`. `name` is reserved for future killer keying, unused today.

- **cosmetic cage** — a cage a setter draws for display, carrying its sum as a
  label rather than as an enforced killer constraint. SudokuMaker forces one
  whenever a killer sum runs out of standard-digit range — the case a **doubler**
  inside a cage creates — because its killer tool refuses to store that sum.
  gridfind reads a cosmetic cage whose label is a number **as a killer cage**; it
  is the only channel an out-of-range sum arrives through (ADR-0008). A cage
  whose label is non-numeric stays inert.

---

## `group-sum` layer

Sum as an N-ary reduction (issue #241, spec #240): a clue names any number of
cells (N >= 2, two is just its smallest case) and a target; the layer sums
their content to it, one rule per clue. Structured like `pair-sum` and the
killer-sum half of `cage` (a clue-looping layer pulling every `group-sum`
constraint via the dispatch), emitting only the total — never an
`add_all_different`, so a bare group-sum carries no implied uniqueness: a
target of 10 over a non-house pair may be met as 5+5. Where a setter wants
distinctness too, it composes alongside this layer rather than folding into
it. S-blind by decision, matching the cage's killer sum: reads the singular
`content()` seam and raises "not Schrödinger-ready yet" over a named S-cell
rather than guessing which of its two digits counts.

- **group-sum** — the constraint and the rule it emits: `{type: group-sum,
  cells: [...], sum}`.

This is purely additive: `pair-sum` and `cage` are unchanged, each still its
own canonical type. `pair-sum` folding into `group-sum` as an XV-only alias,
and a killer cage recomposing as `group-sum` + uniqueness, are separate,
later changes (spec #240).

---

## Modifiers

A cell whose placed digit enters constraint arithmetic changed rather than raw.
The value seam reads a cell's **value**, which is its digit for a plain cell and
its modified amount for a modifier cell — so a sum, difference, or cage total
folds the modifier without the constraint layer knowing one is present.

- **modifier** — a cell that transforms its own digit for arithmetic. Its
  **position is declared** by the setter (a color-marked cell in a SudokuMaker
  link, ADR-0008), while a plain puzzle discovers modifier positions by the
  one-per-house transversal (issue #237). The distinction is placement, not
  value.

- **doubler** — the built modifier: its value is `2·d0`, twice its digit. A
  doubler inside a **cage** is what drives a sum out of standard-digit range and
  forces the setter to a **cosmetic cage**.

A **found** verdict's **witness** reports which cells the solver discovered as
modifiers on a `modifiers: dict[str, str]` field, address to the puzzle's
declared modifier type (`"doubler"`) — the modifier analog of `assignment`,
populated from the discovered `is_modifier` structure the same way `assignment`
is gated on `is_s`. The witness's digit `assignment` still carries the raw
digit, never the folded value: a **given** on a modified cell pins the digit
only (the existing `restrict → d0`), and the value derives from it. Discovered
modifier-ness also gets its own **working-state directive channel**,
`modifier_directives`, mirroring `s_directives` rather than folding into
given/candidate/placement — a modifier's position is discovered, not a digit
fact those channels state (spec #232 decision #218).

---

## `quad-rank` layer

Terms carried over from the quad-rank effort, re-rooted onto the layer model. A
quad-rank layer emits its rules by concatenating cell content over a window
(phase 2), so its **ragged** behavior falls out of composition with the
`schrodinger` layer through the structure registry — the quad-rank layer never
mentions S-cells.

- **rank clue** — names a 2×2 window by its top-left cell and gives that window's
  rank: the digits read TL/TR/BL/BR, concatenated, ranked (SQL `RANK`) against
  every other window — ties share the lower rank, ranks after a tie are skipped.
  (Quad-rank's original **quad-rank clue**.)
- **ragged window** — a 2×2 window whose cells' concatenated content reads as
  **more than four** digits because one or more are S-cells. A window contains 0,
  1, or 2 S-cells. The raggedness is not the quad-rank layer's concept — it is
  what content-concatenation yields when a Schrödinger layer is also in the stack.
- **window value** — how a window ranks once content is concatenated: an S-cell
  contributes both of its digits in reading order, so a ragged window's value is
  longer than a plain window's. (Quad-rank's **S-cell window value**.)
