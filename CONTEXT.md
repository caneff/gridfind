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

The whole point of gridfind: classify a working state as one of three (map #1,
decision 15). The core runs **pure-satisfaction** search — it races a broke-proof
against a witness-find, never an objective solve.

- **found** — a **witness** exists; here it is. The first solution CP-SAT
  returns, with no enumeration and no uniqueness claim.
- **broke** — proven that **no** completion exists (the space is infeasible).
  A change that merely lands on a _different_ valid grid is not broke — that is a
  different valid puzzle. Broke is a consistency claim: does any completion
  exist, never whether one intended solution survived.
- **unknown** — neither decided within the search budget. Carries **no**
  near-miss and no rank-error (both dropped with the objective solve; map #1, out
  of scope).

- **witness** — a concrete full grid satisfying every rule in the stack. The
  proof object returned by **found** — a usable grid, not just a yes.

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
  **this** level and stays retired (map #1, decision 6): CP-SAT's internal
  constraint hides behind _rule_. The word is spoken only one level up, where
  nothing can collide with it — a killer cage is not a solver constraint, it
  becomes several.

- **layer** — a composable, parameterized rule-family module (map #1, decisions
  5, 7). Layers are granular, not monolithic puzzle types: `board`,
  `rows-distinct`, `cols-distinct`, `regions-distinct(region-map)`,
  `line-count-distinct`, and so on. Classic sudoku is
  `board + rows-distinct + cols-distinct + regions-distinct(3×3)`; drop the
  regions layer and it is a Latin square. A layer contributes cells and rules and
  knows no puzzle concepts beyond its own.

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
  (`records`, and `board` after #78; two-channel rule in
  [ADR-0003](docs/adr/0003-two-channels-registry-and-engine.md)). The line between
  the two channels is _who produced the fact_: the registry carries what a layer
  derived, a carried field carries what the setter supplied. Setter input needs
  its own channel because `verdict` and `emit_distinct_count` consume it and
  neither is a layer.

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
  layers. A puzzle is, ultimately, a **stack of layers**.

---

## Working state

The shared-core half of the working-state grammar (map #1, decision 12) — the
directives every grid puzzle understands. Each active layer registers its own
directives on top; a header line declares the active layer stack.

- **working state** — the setter's in-progress hand-solve fed to gridfind: some
  cells placed, others narrowed. The question asked of it is always a verdict —
  "have I broken it yet?"

- **given** — a grid cell the setter has placed to a single digit. Content pinned
  to one value.

- **candidate / pencilmark** — a cell narrowed to a subset of digits (e.g.
  `{2,5,7}`) without being placed. Weaker information than a given.

- **placement** — asserting a digit sits at a cell (`RxCy`) as part of the
  hand-solve. The core-level place directive; layers may refine what a placement
  means for their own cells (see the Schrödinger layer's **bare placement**).

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
- **XV** — the setter-facing variant, two sugar spellings of a pair-sum whose
  target is named rather than written: an **X clue** is a pair-sum of 10, a
  **V clue** a pair-sum of 5.

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
