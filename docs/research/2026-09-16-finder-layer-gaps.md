# Which missing gridfind layers recent hunts needed

Resolves [#797](https://github.com/caneff/gridfind/issues/797), child of the
finders-on-gridfind wayfinder map
([sudokumaker-custom-constraints#478](https://github.com/caneff/sudokumaker-custom-constraints/issues/478)).

## Method

Read the four recent hunts' CP-SAT encodings in
`caneff/drills` (worktree `sudokumaker-custom-constraints/gridfind-integration`):
`finders/renbanana_cpsat.py`, `finders/zombo_brainanas_cpsat.py`,
`finders/ghosts/{connected,shapes}.py`,
`docs/research/2026-09-14-galaxy-copycat/copycat_rsl_solver.py` (+ design
note), and `examples/fillomino/generate.py`. Cross-referenced against
gridfind's layer registry (`src/gridfind/layers/door.py`), `CONTEXT.md`, and
every open `wayfinder:map` ticket (`gh issue list --label wayfinder:map`,
2026-09-16), reading each open sub-map's body and children (#397, #403, #409,
#410, #411, #412, #413, #417, #418, #771, #772).

## Table

| Need | Finder encoding (file:line) | Matching gridfind map/ticket | Answers an open question? |
|---|---|---|---|
| **Free per-cell shading** (background 2-colouring, not part of the solution check) | `renbanana_cpsat.py:213` `self.choc = {p: m.new_bool_var(...)}`; `zombo_brainanas_cpsat.py:158-160` `inf`/`pz` bools | none — no open map scopes a free (non-solution) shading layer | no |
| **"Every maximal same-colour component is a rectangle"** via the "connected + no 2x2 window with exactly 3 of the colour ⇔ rectangle" lemma | `renbanana_cpsat.py:216-223` (Rule 3); `zombo_brainanas_cpsat.py:195-199` (identical lemma, second independent implementation) | none directly — closest is chaos construction (#412, still an uncharted stub: "build orthogonally-connected jigsaw regions"), which is region-discovery but not rectangle-shape-checking | no — #412 is unstarted, and rectangle-shape-of-a-component isn't in its stub catalogue (chaos-construction/-arrow/-count) either |
| **Component-size cap via structural labelling** (each cell in a component picks a label restricted to "min index in the component"; a label covers ≤ k cells) | `renbanana_cpsat.py:227-258` (banana ≤ 9 cells); `zombo_brainanas_cpsat.py:309-330` (label + distance-from-root chain, used for group *counting* not just capping) | connectivity geometry (#418) — a connected-region primitive is exactly what a size-capped label group is, minus the cap | **yes, partially** — this is a *second* connectivity encoding pattern (labelling with a min-index root) that #771 doesn't list. #771 only weighs flow / `AddCircuit` / layered reachability; renbanana's/zombo's label-and-root scheme is closer to "layered reachability" (zombo's `dist` variable literally is a BFS depth) but the renbanana variant skips the distance variable entirely, propagating only an inequality on label vs. index. Worth folding into #771's measurement as a fourth candidate, or noting it's a variant of layered reachability rather than a distinct one. |
| **Connectivity via lazy CEGAR cuts** (solve, flood-fill, cut every non-whole component, re-solve) | `finders/ghosts/connected.py:44-70` (`solve_connected`); also `renbanana_cpsat.py:437-463` (`legal_shading`, cuts rectangular banana components) | connectivity geometry (#418) via encoding ticket #771 | **yes** — #771 asks which of 3 *exact* encodings to use; the finders show a 4th, *inexact-but-lazy* route that never appears in the model up front. It is cheap to add per cut but requires re-solves; #771's bar (single solve <1s on 9x9) is a different question from "how many re-solves to convergence," which these finders answer empirically (renbanana: 33 cuts to first legal shading; ghosts: variable, sometimes non-convergent in the failed CEGAR variant per `docs/research/2026-09-15-ghosts-all-visible.md`). This is evidence *against* CEGAR as gridfind's exact encoding (it's a search technique, not a rule) but is worth citing in #771's writeup as "why not lazy cuts." |
| **Connectivity via single-commodity flow, discovering the region itself (not just testing a fixed set)** | `examples/fillomino/generate.py:94-134` — `rid`/`root`/`flow` vars; root emits its digit's worth of flow, every cell absorbs 1, flow only crosses an edge where both cells hold equal digits | connectivity geometry (#418) → encoding ticket #771; chaos construction (#412) | **yes, directly** — this is real, working, *measured-in-production* evidence for #771's flow candidate, on the connected-region-discovered-at-solve-time shape #412 needs (fillomino: "a region *is* an orthogonally connected component of equal digits," `generate.py:29-31`). #771 is still open and unmeasured; this finder already runs flow successfully for a structurally identical problem (region membership is a decision variable, not fixed) and should be cited as a prior data point before re-measuring from scratch. |
| **Infection/percolation closure** (a digit-ordering "spread" rule: an infected cell infects every smaller orthogonal neighbour, to closure, with an explicit "needs a source or is patient zero" clause) | `zombo_brainanas_cpsat.py:182-194` (`lt`, `spread`, `s`, closure `AddBoolOr([*srcs, pz[p], inf[p].Not()])`) | none — no open map scopes a percolation/reachability-with-an-ordering-condition primitive; closest cousin is connectivity (#418) but that is *undirected* connected-region membership, not directed spread-to-closure | no |
| **Copycat cell: conditional value-equality to a computed partner cell** (value = digit at the grid's 180°-rotated position, gated by a per-cell boolean flag; else value = own digit) | `copycat_rsl_solver.py:146-147` `m.Add(value[r][c] == digit[8-r][8-c]).OnlyEnforceIf(cc[r][c])` / else-branch | none — `rg -uu` for reflect/rotat/mirror/180/opposite in gridfind's `src/`, `docs/adr/`, `CONTEXT.md` turns up no hits outside unrelated matches (`applier.py`, `schrodinger.py` "opposite" in prose, none about geometric reflection) | no. Note: this is *not* the same shape as gridfind's `clone` layer (`layers/clone.py`) — clone equates digit sets between named group members at build time; copycat equates one cell's *value* to another cell's *digit* at a geometrically-derived address, conditionally on a per-cell boolean decided by the solve. The closest existing gridfind pattern is the Schrödinger layer's gated-slot value channel (`value_expr`, ADR-0009/0010) — a per-cell boolean gating an alternate value read — worth citing as prior art if a copycat-style clue is ever chartered, but no map currently scopes it. |
| **Galaxy region (orthogonally connected, 180°-symmetric about its own circle)** — designed in `docs/research/2026-09-14-galaxy-copycat-design.md` but **not implemented** in `copycat_rsl_solver.py`: the shipped solver hard-codes the grid-centre reflection (`digit[8-r][8-c]`) everywhere, never builds a galaxy | n/a — design only, no encoding exists to cite | chaos construction (#412, stub, unstarted) is the natural home (region discovered at solve time) but its own catalogue (chaos-construction/-arrow/-count) doesn't mention point-symmetry-about-a-region-local-centre | no — flag as a **future** need, not a present gap with an encoding to measure |
| **Region-sum lines, split into per-box segments, equal sums per segment** | `copycat_rsl_solver.py:65-72` (`segments`), `:163-167` (per-segment sum equality) | **already covered.** `gridfind/layers/line.py` `_region_sum`, ratified in [ADR-0023](https://github.com/caneff/gridfind/blob/main/docs/adr/0023-region-sum-single-region-totals-ratified-from-spec.md) — per-visit segmentation at region boundaries, exact match to the finder's `segments()` helper | n/a — not a gap. The finder independently re-derived a rule gridfind already ships; no promotion needed. |
| **Ghost neighbour-count clue**: a cell's digit equals the count of "ghost" (shaded) cells among its 8 neighbours, with the count distinct within every row/column/box among ghost cells | `finders/ghosts/connected.py:81-89` (`n[i] == sum(g[j] for j in NEIGH[i])`, then pairwise `!=` within units) | none — no open map or existing layer does "count of a free boolean among king-neighbours, read as the cell's own digit." `offset_adjacency.py`'s `OffsetAdjacency`/`OffsetValueGap` forbid same-digit or enforce a value gap at fixed offsets; neither counts. | no |

## Search-strategy items (should never be a layer)

These are how a finder *looks for* a witness, not a rule the witness must
satisfy — they belong in `finders/hunt/` (per map #478's decision) or a
CEGAR helper, never in `gridfind/layers/`:

- **Uniqueness-by-cut / CEGAR** (solve → find a second solution or an
  illegal shape → forbid exactly that pattern → re-solve): renbanana's
  `legal_shading`/`forbid_component`/`forbid_shading`
  (`renbanana_cpsat.py:399-463`), ghosts' `solve_connected`
  (`connected.py:44-70`), zombo's `cuts` parameter
  (`zombo_brainanas_cpsat.py:224-232`). gridfind already has the *exact*
  alternative for uniqueness (`enumerate_witnesses`, map #1 decision #382);
  these finders use cuts instead because their master models are cheap to
  re-solve and mutate. This is a hunt-loop pattern, not a gridfind rule.
- **Shape/hill-climb search seeded from a joint CP-SAT feasibility model**,
  then locally toggled (ghosts' `shapes.py`, `fastclimb.py`,
  `ghosts_fast.c`): a search metaheuristic layered *on top of* a fixed rule
  set, not a rule itself.
- **Objective-function diversity weighting** (random per-variable noise on
  both shading and digits, Hamming-distance/shape-multiset dedup): pure
  search-diversity machinery, orthogonal to any clue's semantics.
- **Two-stage decomposition** (shading-only stage 1, digits-on-fixed-shading
  stage 2/3 in renbanana and zombo): a solve-order strategy exploiting that
  the shading is far more constrained than the digits; not a rule.
- **Lazy per-violation cuts vs. one exhaustive clause per shape** (zombo's
  comment at `zombo_brainanas_cpsat.py:195-199` notes it replaced ~2025
  lazy cuts with one `AddBoolOr` per legal rectangle placement, "replaces
  the lazy per-violation cuts, which cost a full re-solve each"): an
  encoding-tuning decision about the *same* rule, not a second rule.

## Proposed follow-ups (not filed — listed per task instructions)

1. Fold the renbanana/zombo **labelled-component-with-min-index-root**
   pattern into #771 as a candidate/variant of layered reachability, with a
   note on the "component-size cap" variant (renbanana) vs. the
   "count-of-components" variant (zombo, adds a `dist` BFS-depth variable).
2. Cite `examples/fillomino/generate.py`'s single-commodity flow encoding as
   existing, measured evidence for #771's flow candidate on the
   discovered-region shape, before re-prototyping from scratch.
3. A gap issue for **"every maximal component of a free shading is a
   rectangle"** as a rule distinct from #418's plain connected-region and
   #412's jigsaw-region-of-equal-value — two independent finders
   (renbanana, zombo) hand-derived the identical "no 2x2 window with exactly
   3" lemma, which is exactly map #478's promotion bar ("promoted once a
   second finder needs it").
4. A gap issue for **infection/percolation closure** (directed spread to a
   fixed point under an ordering condition) — no existing map covers it.
5. A gap issue for **ghost/king-neighbour counting clues** — no existing
   layer counts a free boolean over an adjacency offset set.
6. Note the copycat solver's gap between the *designed* galaxy-local-centre
   reflection (`docs/research/2026-09-14-galaxy-copycat-design.md`) and the
   *shipped* grid-centre-only solver, for whoever picks up chaos
   construction (#412) or a future copycat/galaxy map.

## Out of scope

Porting renbanana/zombo/ghosts onto gridfind — ruled out in the map #478
charting grill ("their value is their bespoke search, not shared plumbing").
This doc only maps *rules*, not code, onto gridfind's roadmap.
