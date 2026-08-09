# Reference: ISS design decisions, and gridfind's stance on each

A comparison map. ISS (the [Interactive Sudoku Solver](https://github.com/sigh/Interactive-Sudoku-Solver)
by `sigh`, MIT-licensed) is the most mature open-source variant-sudoku engine we
know of. This doc records the design decisions ISS made, why, and **gridfind's
deliberate stance on each** — mirror, deviate, not-applicable, or open.

The point is decision-level comparison. When gridfind faces a design fork, look
it up here first: ISS has almost certainly already hit it. Then decide, and if we
deviate, do it **knowingly** and record why (in the relevant ADR, not here).

## How to use this doc

- **Reference copy of ISS source:** `~/src/reference/Interactive-Sudoku-Solver`
  (a shallow clone, outside this repo so it never dirties the checkout). Pinned
  read below is at ISS commit `2e386f8`. Re-`git pull` it when you need current
  source; the *decisions* here are stable architecture and drift slowly.
- **Best primary sources inside that clone:** `js/solver/SOLVER_ENGINE.md`,
  `js/solver/README.md`, `js/README.md`, `js/solver/handler_docs/*.md`,
  `js/sudoku_constraint.js` (the constraint model), `js/solver/sudoku_builder.js`
  (the dispatch), `js/cell_geometry.js` (geometry).
- **Stance tags:** **MIRROR** (adopt), **DEVIATE** (chose differently on
  purpose), **N/A — CP-SAT** (ISS hand-rolls what OR-Tools gives us free), **OPEN**
  (undecided; links to a wayfinder issue).

## The one fault line that colors everything

**ISS is a hand-rolled propagator; gridfind delegates solving to CP-SAT
(OR-Tools).**

ISS runs its own constraint-satisfaction loop: backtracking search + constraint
propagation to a fixed point, over 16-bit candidate bitmasks, in a Web Worker.
Roughly half of ISS's engineering is *inside* that loop — the propagation queue,
per-branch backtrackable state, conflict-score search heuristics, no-allocation
hot paths, and hand-written arc-consistency algorithms (e.g. Régin filtering for
the distinct-count constraint).

gridfind builds one CP-SAT model and hands it to the OR-Tools portfolio solver
(see `ADR-0001`, `verdict.py`). **Everything ISS does inside its propagation loop,
CP-SAT does for us.** So a large class of ISS decisions is marked **N/A — CP-SAT**
below: they are real, careful decisions, but they answer a problem gridfind chose
not to have. The decisions that *do* transfer are at the **modeling and
organization** layer — how constraints are represented, dispatched, composed,
addressed, serialized, and extended. That layer is where ISS is worth mirroring
and where our open questions live.

Read the N/A entries anyway: each names something to *not* reinvent, which is the
lazy win.

---

# Part 1 — Decisions that transfer (modeling & organization)

## 1.1 Three-layer split: spec → builder → handler

**ISS decision.** Three distinct layers, fully decoupled:
- **Constraint spec** (`SudokuConstraint.*`, static inner classes of
  `SudokuConstraint` extending `SudokuConstraintBase`): the user/serialization
  representation of a rule. Pure data + declarative metadata; **no solving logic**.
- **Builder** (`SudokuBuilder.build`): the single bridge. A big `switch` on
  `constraint.type` maps one spec to **one or more** handlers.
- **Handler** (`SudokuConstraintHandler.*`): the runtime enforcement object (a
  *propagator* in CSP terms). Knows nothing about the UI or serialization.

`sudoku_constraint.js` imports **no** handler class; `handlers.js` imports no spec
class. The builder is the only place that knows both.

**Why.** One rule is seen by four audiences — UI, serializer/parser, help-page
generator, solver — and each wants a different projection. Keeping the declarative
description separate from the enforcement code lets each audience read the spec
without dragging in the solver, and lets a spec expand into several handlers.

**gridfind stance: MIRROR the split, DEVIATE on multiplicity — decided (#41, #44).**
All three layers now exist. The **spec** is `Puzzle`'s typed `Constraint`
(`puzzle.py`, #41 — the old text grammar is gone). The **builder** is
`resolve_constraints` reading `LAYER_REGISTRY` (`layers/__init__.py`, #44). The
**handler** is the layer's `emit`. ISS's shape held up: a spec object with zero
solving logic, and a single dispatch chokepoint. SudokuMaker is the cautionary
opposite (logic lives in authored, order-dependent code).

Where gridfind deviates: **many constraints of one type resolve to one stateless
layer, not to one handler each** (#65). ISS's builder instantiates a handler per
spec; `resolve_constraints` dedups by `type`, and the layer pulls its own clues
back out via `engine.constraints_of(name)` and loops them in `emit`
(`pair_sum.py`). ISS needs per-instance handlers because each one owns
propagation state across the search; a gridfind layer owns none, so one instance
serves every clue of its type.

## 1.2 Builder is a single dispatch chokepoint; one spec → many handlers

**ISS decision.** All `type → handler(s)` mapping lives in one `switch` in
`SudokuBuilder`. It is routinely one-to-many:
- `Cage` → a `Sum` handler **+** an `AllDifferent` handler
- `Arrow` → `Sum.makeEqual(circle, shaft)`
- `AntiKnight` → many `BinaryConstraint` instances, one per knight-move pair
- `Thermo` → a chain of pairwise strictly-increasing `BinaryConstraint`s

**Why.** One place to read the entire vocabulary; specs stay small and declarative
while the messy expansion lives in the builder.

**gridfind stance: MIRROR the chokepoint, DEVIATE on mechanism — built (#44).**
gridfind already has one-to-many inside a layer (`regions-distinct` loops regions;
`line-count-distinct` loops rows). The dispatch mechanism is the
**`LAYER_REGISTRY` dict** (`type → Layer`), read by `resolve_constraints` — not a
literal `switch`. ISS uses a switch partly because JS lacks a clean class registry;
Python's dict-of-instances *is* that registry. Same chokepoint idea, lazier
mechanism.

One pass sits in front of dispatch: `expand_constraints` resolves **presets**
(`sudoku` → the three bare distinct constraints) and **aliases** (`x` → `pair-sum`
with `sum: 10`) before any type reaches the registry, so dispatch and identity
(4.2) both see canonical constraints.

## 1.3 Declarative metadata on the spec drives UI, help, parser

**ISS decision.** Each spec class declares static metadata that other subsystems
read reflectively:
- `DESCRIPTION` — human text, feeds the auto-generated help page.
- `CATEGORY` — taxonomy (see 1.4); drives UI grouping and composite-nesting rules.
- `DISPLAY_CONFIG` — how to draw it (colors, line width, markers).
- `ARGUMENT_CONFIG` — the input widgets for its parameters.
- `UNIQUENESS_KEY_FIELD` — which field identifies "the same constraint" (see 4.2).

The UI, help generator, and parser are generic over this metadata — adding a
constraint type lights them all up with no per-type UI code.

**Why.** A constraint type is defined once; every surface derives from that one
definition instead of maintaining a parallel table.

**gridfind stance: DEVIATE for now (no second surface yet), MIRROR the instinct.**
gridfind has no UI, no help page, no drawing. The only "other surface" was the
working-state grammar, and #41 removed it in favor of the `Puzzle` object. So
most of this metadata (`DISPLAY_CONFIG`, `ARGUMENT_CONFIG`) is YAGNI. But two
fields have gridfind analogs worth keeping in mind: `CATEGORY` (see 1.4) and
`UNIQUENESS_KEY_FIELD` (maps to gridfind's identity-keying, [#33] / 4.2). If a
`Puzzle`-authoring UI or a variant catalog ever appears, revisit — the "one
declaration, many surfaces" pattern is the right target then.

## 1.4 A constraint taxonomy (categories)

**ISS decision.** Every constraint has a `CATEGORY`. The set in use:
`LinesAndSets` (35 of them — the bulk), `LayoutCheckbox`, `OutsideClue`, `Global`,
`Region`, `Shape`, `Experimental`, `StateMachine`, `Pairwise`, `GivenCandidates`,
`Composite`, `ChaosConstruction`. Category is not cosmetic: it gates
composite-nesting safety (1.7) and organizes the UI.

**Why.** ~70 constraint types need grouping for humans and need behavioral classes
for the engine (e.g. "which types are safe to nest under `Or`").

**gridfind stance: OPEN, low priority.** gridfind has ~6 layers; a taxonomy is
premature. But note the axes ISS found useful, because gridfind will grow the same
distinctions: **global vs. local** (whole-grid rule vs. drawn-on-cells rule — this
is also SudokuMaker's primary axis), **layout/shape vs. value rule**, and
**composite vs. leaf**. When gridfind passes ~15 variant types, adopt a small
category field. Not before.

## 1.5 Relation-as-data: one pairwise primitive, parameterized by the relation

**ISS decision.** A huge family of variants is "a binary relation between two
cells." ISS has **one** `BinaryConstraint` handler parameterized by a **precomputed
truth table** (a lookup key decoded via `LookupTables`). Thermo (`<`), kropki,
XV, anti-consecutive, whispers — all are the same handler with different table
data, not bespoke classes. There is even a `Pairwise` category and a sandbox path
that compiles a user's `(a,b) => boolean` into such a table.

**Why.** Writing one propagator and expressing each relation as data collapses a
whole variant family to configuration.

**gridfind stance: MIRROR the idea, DEVIATE on the encoding — this is [#42].**
Adopt "one parameterized pairwise helper" instead of a layer class per pairwise
variant. But **do not** copy the truth-table encoding: ISS needs a table because
it hand-propagates; CP-SAT lets us write `model.add(a < b)` directly, which is
lighter and clearer. So gridfind's version is a helper taking a per-pair OR-Tools
expression (`lambda a, b, model: ...`), the sibling of the existing
`_base.emit_distinct_count`. Only reach for a table/allowed-assignments encoding
if a `Puzzle` ever carries a *setter-defined* relation as data (it doesn't today —
`type` fixes the relation). Timing: the helper waits for the **second** two-cell
variant, not the first. `pair-sum` (#66) shipped and deliberately emits its sum
rule directly rather than inventing a shared helper for a single caller
(`pair_sum.py`). **Still OPEN, and the only one with a filed issue** — 1.4, 1.6 and
5.4 are also OPEN but deferred until gridfind meets the problem at all. See [#42].

## 1.6 Sequential / line constraints via NFA

**ISS decision.** Ordered-sequence rules (palindrome, whisper line, renban,
region-sum line, zipper, arbitrary regex, arbitrary JS state machine) are enforced
by **one** `NFAConstraint` handler driven by a compressed nondeterministic finite
automaton. `nfa_builder.js` builds the NFA three ways: `regexToNFA` (Thompson
construction), `javascriptSpecToNFA` (a user `(state, symbol) → state` machine),
and `optimizeNFA`. Enforcement is a forward + backward layered pass for arc
consistency along the line.

**Why.** "A property of the sequence of digits along a path" is a second giant
variant family (after pairwise). An NFA is a single, composable representation for
all of them, and it doubles as a scripting extension point.

**gridfind stance: OPEN, future — but flag the encoding question early.** gridfind
has no line/path variants yet. When they arrive (renban, whisper, palindrome), the
question is *how to encode a sequence rule for CP-SAT*. Options CP-SAT gives us
that ISS can't lean on: `add_automaton` (CP-SAT has a native regular/automaton
constraint — a close match to ISS's NFA, but the solver does the propagation),
direct pairwise decomposition (whisper = pairwise `|a-b|≥k` along the path — often
just [#42]'s helper), or `add_allowed_assignments` over a window. **Prefer letting
CP-SAT's `add_automaton` do what ISS's NFA machinery does by hand.** Record the
decision when the first line variant lands. Cross-refs: `add_automaton`,
`add_allowed_assignments`.

## 1.7 Composition: flat list + explicit composite (`Or`/`And`) with nesting rules

**ISS decision.** Two layers of composition:
- **Implicit:** handlers are a flat list keyed by the cells they touch. When a
  cell changes, every handler on that cell re-runs. No merging; constraints
  coexist by sharing cell indices.
- **Explicit:** `Or`/`And` composite constraints (category `Composite`). `Or`
  speculatively enforces each branch on a scratch copy of the grid and unions the
  survivors. Nesting is **gated by category**: `CompositeConstraintBase._ALLOWED_CATEGORIES`
  rejects any constraint whose handler reads per-branch state written by *another*
  handler (documented at length in `SOLVER_ENGINE.md` → "Composite safety"). A
  whole invariants doc (I1–I12) backs it.

**Why.** Most composition is free (share cells). Genuine disjunction ("this cage
OR that cage") needs real machinery, and that machinery is only sound for handlers
that obey strict locality invariants — hence the allowlist.

**gridfind stance: MIRROR implicit (already cleaner), DEVIATE/DEFER explicit.**
gridfind's structure registry + two-phase build is a *tidier* version of implicit
composition: build-time wiring, zero solve-time cost, layers reference each other
through named structures rather than shared indices (`CONTEXT.md` → structure
registry, decision 9). Keep that. For **explicit disjunction**, gridfind gets it
almost free: an "OR of constraints" is a reified-bool / `add_bool_or` /
channeling pattern in CP-SAT — no scratch-grid speculation, no per-branch-state
allowlist. ISS's entire composite-safety apparatus is **N/A — CP-SAT** (it exists
because ISS hand-unions propagation state). gridfind's related concept is the
**bridge layer** (`CONTEXT.md`) for pairs that can't reconcile through cell content
— a different, more principled mechanism. No action; note the parallel.

## 1.8 Grid cells vs. "var cells" (cells outside the grid)

**ISS decision.** Beyond the 2D grid, ISS has **var cells**: user-declared cells
outside the grid (arrow totals, etc.), managed by `VarCellRegistry`, addressed
**uniformly** with grid cells (same integer-index space, same search). Grid cells +
var cells = "search cells."

**Why.** Many variants need a value that isn't on the board. Making outside cells
first-class and uniformly addressed means the solver core needs no special case.

**gridfind stance: MIRROR — already designed in.** gridfind's `CONTEXT.md` already
names **grid cell** vs. **outside cell** ("an arrow target, a room member … obeys
no grid rule, participates only through clues that name it"). ISS confirms the
design and the key discipline: outside cells share the cell/variable machinery and
differ only in which rules touch them. When gridfind builds its first outside-cell
variant (killer-cage total shown outside, arrow), keep them ordinary `Cell`s that
simply aren't in the `grid` structure.

---

# Part 2 — Addressing, geometry, representation

## 2.1 Cells are integer indices internally; cellId strings only at the boundary

**ISS decision.** Inside the solver a "cell" is **always an integer index**.
`"R1C1"` strings ("cellIds") exist only at the UI/serialization boundary and are
converted **once** at build time. Handlers never see strings.

**Why.** Speed and simplicity: index arithmetic, typed arrays, no string parsing
in the hot loop.

**gridfind stance: DEVIATE, deliberately, but watch the boundary.** gridfind's
`board` stores the grid as cell **names** (`RxCy` strings) on purpose: name→variable
resolution is deferred to phase 2 so a Schrödinger layer can widen a cell's content
first (`_base.grid_content` documents exactly this). That is the right call for
gridfind — CP-SAT variables, not indices, are the currency, and the deferral buys
Schrödinger composition. The transferable discipline is the same as ISS's: **do the
address→content resolution once, at a single chokepoint** (`grid_content`), not
scattered. Keep it there.

## 2.2 Geometry as a separate descriptor object (`CellGeometry`)

**ISS decision.** `CellGeometry` is a standalone "structural descriptor": grid
dimensions, value range/offset, the cellId↔index codec, var-cell groups, and cell
adjacency (`CellGraph`: neighbours, rays, chess-move pairs). It holds **metadata
only — no candidates, no state**. Handlers receive it at `initialize`. Supports
1×1 to 16×16, including non-square. Note the deliberate split: `CellGeometry` (the
runtime descriptor) is distinct from the `Shape` *constraint* (the serialized
declaration of geometry).

**Why.** Geometry is a pure function of the puzzle's shape, needed everywhere but
owned by nobody in particular. Centralizing it keeps every handler size-agnostic
and keeps adjacency queries out of individual constraints.

**gridfind stance: MIRROR, decided in [ADR-0004](../adr/0004-binding-not-provenance.md) (#43).**
- Geometry-lives-in-a-layer: **reversed.** It used to be mirrored the other way —
  `board` owned all geometry and published the address grid to the **structure
  registry**, so `verdict` had to cast its way in. ADR-0004 adopts ISS's split:
  a `CellGeometry` descriptor built from the setter's board before any layer
  runs, holding the size, the digit values, the box tiling, and the `RxCy`
  addresses, readable by anyone.
- Adjacency queries (knight-move pairs, orthogonal neighbours, along-a-line):
  **a slot in `CellGeometry`, unbuilt.** ISS centralizes these in `CellGraph`;
  gridfind will too when the first adjacency variant lands. The earlier lean —
  a `_geometry` helper deriving adjacency from the `grid` structure — survives
  only as the free function that builds the descriptor.
- Size/shape as data not syntax: **already aligned** — #41 makes board size/box a
  `Puzzle` field, mirroring ISS's `Shape`. Hex is out of scope for gridfind (a
  different board family), where ISS supports non-square; don't over-build for it.

## 2.3 Value representation: 16-bit candidate bitmask

**ISS decision.** Each cell's live candidates are a 16-bit mask (bit *i* = value
*i+1*). `LookupTables` precomputes `sum[mask]`, `rangeInfo[mask]` (min/max/isFixed),
`reverse[mask]` for every possible mask. Set ops are single bitwise instructions.

**Why.** It's the state a hand-rolled propagator mutates millions of times;
bitmasks make intersection/union/count one instruction and cap the grid at 16
values.

**gridfind stance: N/A — CP-SAT.** gridfind's `Cell.content` is a sequence of
plain integer CP-SAT variables (`CONTEXT.md`: "Domains are plain integer only; a
layer may add a one-hot channel locally for one rule if it wants"). CP-SAT owns
the candidate representation and its propagation. The one echo: a layer that *wants*
set-style reasoning adds a **one-hot bool channel** locally — the CP-SAT-native
analog of a mask — which is exactly what `emit_distinct_count` does with its
per-digit reified bools. No global bitmask, no `LookupTables`.

---

# Part 3 — Extension & scripting

## 3.1 Two extension tiers: first-class type vs. sandbox script

**ISS decision.**
- **First-class:** add a `SudokuConstraint.*` subclass (with metadata) + a builder
  `case`. Lights up UI/help/parser automatically.
- **Sandbox:** a Web-Worker JS environment (`js/sandbox/env.js`,
  `user_script_worker.js`) exposing `parseConstraint`, `parseCellId`,
  `makeCellId`, a `cellGraph` with `row/column/box/neighbours/ray/step`,
  `makeSolver`, the `SudokuConstraint` namespace, and geometry constants. User code
  returns constraint objects/strings; custom logic compiles to a `BinaryConstraint`
  table or an `NFAConstraint`.

**Why.** Two audiences: contributors extending the tool (first-class) and setters
prototyping a novel rule without a rebuild (sandbox).

**gridfind stance: DEVIATE — no third-party extension by design (today).**
`ADR-0001` records that gridfind has **no external or plugin callers**; every layer
is in-tree. So the sandbox tier is out of scope, and "first-class" is just "write a
layer." The relevant lesson isn't the sandbox itself but ISS's proof that **custom
logic reduces to two primitives** (pairwise table + NFA). gridfind's equivalent
future primitives are [#42]'s pairwise helper and 1.6's automaton path. If a
`Puzzle`-level custom-constraint feature is ever wanted, those two are the surface
to expose — not raw CP-SAT.

## 3.2 The sandbox reuses the real solver

**ISS decision.** Sandbox scripts call `makeSolver()` / `solverLink()` — the same
engine, not a reimplementation. SudokuMaker does the same (its custom-constraint
`validate` runs the real candidate-elimination loop).

**Why.** One solver to trust; test-solving a prototype uses production logic.

**gridfind stance: MIRROR (already true).** gridfind has exactly one solving seam,
`verdict()` (`ADR-0001`: "the one seam"). Anything that needs to check
satisfiability goes through it. Keep it the only door.

---

# Part 4 — Serialization, identity, uniqueness

## 4.1 Canonical string serialization; full state in the URL

**ISS decision.** Constraints serialize to a dot/tilde string
(`.Thermo~R1C1~R2C1`); the whole puzzle lives in a URL query param (`q`). A
multi-format `SudokuParser` also reads plain-text grids, killer shorthand, and
jigsaw layouts into the same constraint objects.

**Why.** URL-as-state gives free sharing, bookmarking, and undo/redo history.

**gridfind stance: DEVIATE — JSON, not a string grammar.** #41 made the durable
form **JSON `Puzzle`/`WorkingState`** (`puzzle.py`) and removed the old text
grammar; both round-trip to an *equal* object. That's a
conscious divergence from ISS's string form, and the right one: gridfind's input is
structured data consumed by code (corpus files, a screenshot reader), not a URL a
human pastes. SudokuMaker's URL-blob approach (whole puzzle + custom-constraint code
LZ-compressed into the URL) is an explicit anti-pattern to avoid — it hits
URL-length limits. Keep gridfind's durable form JSON; a builder API is sugar over
the same object.

## 4.2 Constraint identity / uniqueness key

**ISS decision.** `UNIQUENESS_KEY_FIELD` names the field that identifies "the same
constraint" for dedup (e.g. an outside clue keyed by `arrowId`, a region by
`cells`). `HandlerSet` also dedups handlers by a stable `idStr`.

**Why.** Adding the same clue twice, or two specs that reduce to the same handler,
shouldn't double-constrain or bloat the model.

**gridfind stance: MIRROR — decided and built (#33, #41).** `canonical_identity`
keys a puzzle on its expanded constraint set, alphabetically sorted, so the preset
spelling and the explicit spelling compare equal. That **is** ISS's uniqueness-key
idea one level up, and ISS validates the ordering: **normalize/expand first, then
key on the expansion** (its `SudokuParser` normalizes before build;
`expand_constraints` plays the same role). Expansion and dispatch stayed separate
passes, so keying sees canonical constraints.

**Watch item.** `canonical_identity` keys on constraint `type` only, and its own
`ponytail:` note says to fold params in "when data-bearing variants land." `pair-sum`
(#66) has landed and carries `cells` + `sum`, so two pair-sum puzzles differing only
by their clues share an identity. Harmless today — the sole caller is corpus
grouping in `population_test.py`, where same-stack-same-bucket is the intent — but
the stated trigger has fired, so re-read the note before identity gains a second
consumer.

---

# Part 5 — Solving strategy & modes

## 5.1 Solver modes: count, uniqueness, nth-solution, all-possibilities, estimate

**ISS decision.** `SudokuSolver` exposes `countSolutions(limit)`,
`estimatedCountSolutions` (random sampling), `nthSolution`, `nthStep` (step-by-step
UI), `solveAllPossibilities(threshold)` ("true candidates" — values appearing in ≥
threshold solutions), and `validateLayout`.

**Why.** A *solving* tool wants to enumerate, prove uniqueness, and visualize the
solution space, not just find one grid.

**gridfind stance: DEVIATE, decided — gridfind is a *verdict* tool, not a solver.**
`CONTEXT.md` is explicit: the whole point is classify **found / broke / unknown**,
"the first solution CP-SAT returns, with no enumeration and **no uniqueness
claim**." Uniqueness, counting, near-miss, rank-error were all deliberately dropped
(map decision 15, out of scope). So ISS's mode menu is intentionally *not*
mirrored. If uniqueness is ever wanted, CP-SAT does it with a second solve /
solution callback — but that reopens a settled scope decision, so it needs a new
ADR, not a quiet addition.

## 5.2 Search heuristics, propagation queue, backtracking, no-alloc hot loop

**ISS decision.** An explicit-stack DFS (no recursion) over a shared `ArrayBuffer`;
a `PropagationQueue` drained to a fixed point; `CandidateSelector` ranking cells by
conflict-score ÷ candidate-count with MRV fallback; per-branch backtrackable state
via a state allocator (with bit-packing); a strict "no allocations in
`enforceConsistency`" rule.

**Why.** This is the performance core of a hand-rolled CSP solver.

**gridfind stance: N/A — CP-SAT owns all of it.** Variable/value selection,
propagation, backtracking, restarts, and its portfolio of workers are OR-Tools'
job (`verdict.py` sets `num_workers`, `max_time_in_seconds`). gridfind should
**never** hand-roll any of this. `verdict.py` runs CP-SAT's default
pure-satisfaction search directly — no gridfind-side seam configures it
(ADR-0005).

## 5.3 The optimizer: derive redundant constraints for speed

**ISS decision.** Before search, `SudokuConstraintOptimizer` adds **logically
redundant** handlers that don't change the solution set but speed propagation:
innie/outie sums where a cage overlaps a house, merged adjacent sums, `House`
handlers over full rows/cols/boxes, exclusion transitivity (A=B, A≠C ⟹ B≠C).
Derived handlers are marked `essential=false`.

**Why.** Human solvers exploit these deductions; a hand-rolled propagator gets them
only if you add them. Big speedups, zero correctness change.

**gridfind stance: N/A — CP-SAT presolve, mostly.** OR-Tools' presolve derives
implied constraints, does probing, and detects `AllDifferent`/cardinality structure
automatically. gridfind gets the *category* of benefit for free. **Caveat worth
remembering:** presolve isn't omniscient. If a specific variant ever solves slowly,
the ISS lesson is that **hand-adding a redundant rule** (an extra `add_all_different`
over an implied house, an innie/outie sum) can help CP-SAT too — the same idea,
applied as an optional emit, not a whole optimizer pass. Reach for it only on a
measured slow case, never speculatively.

## 5.4 Region discovery (chaos construction)

**ISS decision.** A `ChaosConstruction` family discovers an *unknown* region
layout: partition the grid into connected, distinct-value regions found by solving,
not given. Backed by union-find shard state (`connected_handler.js`,
`chaos_handler.js`, and a dedicated `handler_docs/chaos_construction.md`).
Connectivity itself is a constraint (`ConnectedValues`: cells holding a value form
one orthogonally-connected region, via BFS + one-door forcing).

**Why.** "The regions are part of the solution" is a real variant class, and
connectivity is a genuinely hard constraint needing custom propagation.

**gridfind stance: OPEN, far future; connectivity is the hard part.** gridfind's
`regions-distinct(region_map)` handles *given* irregular regions
(`_irregular_demo_region_map`). *Discovering* regions, or any connectivity rule
(e.g. a snake/path variant), is unbuilt. When it comes, CP-SAT can express
connectivity (`add_circuit`, or reachability via flow/`add_multiple_circuit`), so
the ISS shard/BFS machinery is again a hand-rolled thing CP-SAT can shoulder — but
connectivity is genuinely awkward in any solver, so budget for it. Cross-refs:
`add_circuit`, network-flow formulations.

---

# Part 6 — Counting constraints (a worked comparison)

gridfind already has a counting rule (`line-count-distinct`), so this is the one
place to compare *implementations*, not just decisions.

**ISS decision.** The `CountDistinct` handler enforces **NValue**
(`value(control) = number of distinct values among counted cells`) with a genuinely
sophisticated custom propagator (`handler_docs/count_distinct.md`): the max side is
**exact GAC** via maximum bipartite matching + Régin filtering on the value graph;
the min side is a **sound under-approximation** via greedy disjoint-domain packing
(the exact min is NP-hard). Plus a static lower bound from mutually-exclusive
groups. Hundreds of lines of careful, no-allocation bitmask code.

**gridfind's version.** `_base.emit_distinct_count`: for each candidate digit, a
reified "present" bool (`add_max_equality` over per-cell equality indicators), then
`sum(present) == target`. A dozen lines. CP-SAT does all the propagation.

**Stance: DEVIATE, and this is the fault line in miniature.** ISS *must* write a
world-class NValue propagator because its engine only does what its handlers do.
gridfind writes the *constraint* (reified presence + a sum) and lets CP-SAT
propagate it. gridfind's version is shorter, obviously correct, and as strong as
CP-SAT's engine — we inherit arc-consistency effort we never wrote. **The general
principle:** where ISS's answer to a hard constraint is "a clever propagation
algorithm," gridfind's answer is "state the relation in CP-SAT primitives and stop."
Read ISS's algorithm to understand the *constraint's semantics* (the NValue interval
lemma is genuinely clarifying), not to reimplement its propagation.

---

# Appendix — Quick stance table

| # | ISS decision | gridfind stance |
|---|---|---|
| 1.1 | spec → builder → handler split | **MIRROR** — built (#41, #44); **DEVIATE**: one stateless layer per type, not a handler per clue |
| 1.2 | single builder chokepoint, 1→many | **MIRROR** chokepoint, **DEVIATE** to a dict registry — built (#44) |
| 1.3 | declarative metadata drives UI/help/parser | **DEVIATE** now (no 2nd surface), keep the instinct |
| 1.4 | constraint taxonomy (`CATEGORY`) | **OPEN**, low priority; note global-vs-local axis |
| 1.5 | relation-as-data pairwise primitive | **MIRROR** idea, **DEVIATE** encoding — **OPEN [#42]**, waits for the *second* two-cell variant |
| 1.6 | sequential rules via NFA | **OPEN** — prefer CP-SAT `add_automaton` |
| 1.7 | flat composition + `Or`/`And` w/ nesting rules | **MIRROR** implicit; explicit is **N/A — CP-SAT** |
| 1.8 | grid cells vs. var (outside) cells | **MIRROR** — already in CONTEXT.md |
| 2.1 | integer indices internal, cellId at boundary | **DEVIATE** (names→vars deferred), keep one chokepoint |
| 2.2 | geometry descriptor `CellGeometry` | **MIRROR** ownership — settled in ADR-0004 (#43); adjacency is a declared slot, unbuilt |
| 2.3 | 16-bit candidate bitmask + LookupTables | **N/A — CP-SAT**; one-hot channel locally if needed |
| 3.1 | first-class vs. sandbox extension | **DEVIATE** — in-tree only (ADR-0001) |
| 3.2 | sandbox reuses the real solver | **MIRROR** — one seam (`verdict`) |
| 4.1 | string serialization, URL state | **DEVIATE** — JSON Puzzle, built (#41); avoid URL blob |
| 4.2 | uniqueness key / dedup | **MIRROR** — built as `canonical_identity` (#33); keys on `type` only, see watch item |
| 5.1 | rich solver modes (count/uniqueness/…) | **DEVIATE**, decided — verdict tool, not solver |
| 5.2 | search heuristics, propagation, backtracking | **N/A — CP-SAT** owns all |
| 5.3 | optimizer derives redundant constraints | **N/A — CP-SAT** presolve; hand-add only on measured slow case |
| 5.4 | region discovery + connectivity | **OPEN**, far future; use CP-SAT `add_circuit` |
| 6 | CountDistinct GAC propagator | **DEVIATE** — state the relation, let CP-SAT propagate |

_Pinned to ISS commit `2e386f8`. Update the clone and revisit when gridfind hits a
new fork; record actual decisions in ADRs, not here._

_Stances last reconciled against the repo 2026-08-09: #33, #41, #43 and #44 have
closed since the first draft, so rows 1.1, 1.2, 2.2, 4.1 and 4.2 moved off OPEN.
**[#42] (1.5) is now the only OPEN row with a filed issue**; 1.4, 1.6 and 5.4 stay
OPEN as deferrals — gridfind has not met those problems yet, and no issue tracks
them. When a stance here says OPEN and names an issue, check the issue is still
open before trusting it._
