# ADR-0014: one marking→meaning table for a Schrödinger cell's digit channels

- **Status:** Accepted
- **Date:** 2026-08-14
- **Amended:** 2026-08-14 — a named `S-cell`/`Schrödinger` block's *presence*
  enables Schrödinger mode even when it names no cells, and the default
  Schrödinger digit domain is `0…N` (spec
  [#371](https://github.com/caneff/gridfind/issues/371), ticket
  [#372](https://github.com/caneff/gridfind/issues/372)). This joins
  *enablement by presence* to the *declaration by membership* that map
  [#342](https://github.com/caneff/gridfind/issues/342) recorded — see
  "Presence enables the mode; membership pins" below.
- **Decides:** the single authoritative reading of how a SudokuMaker link's
  markings settle a Schrödinger cell — which channel names the S-cell position,
  which supplies its digits, and what a cell's own center marks and settled
  digits mean once a marker cage is present (spec
  [#347](https://github.com/caneff/gridfind/issues/347), from wayfinder map
  [#342](https://github.com/caneff/gridfind/issues/342); ticket
  [#352](https://github.com/caneff/gridfind/issues/352)).

## Context

Three sibling tickets rebuilt how a link marks an S-cell, each landing one
channel: a settled large digit became a **singleton pin**
([#348](https://github.com/caneff/gridfind/issues/348)); the marker cage's own
`value` became the pair source
([#349](https://github.com/caneff/gridfind/issues/349)); and the cell's center
marks stopped selecting the directive and became a consistency layer over it
([#350](https://github.com/caneff/gridfind/issues/350)). Each ticket updated
`CONTEXT.md` in its own diff. This ADR gathers the result into one table so a
reader settles any marking against a single record instead of reassembling it
from three merged branches.

The channels split cleanly by job. **ADR-0012** decides *which cage name*
declares an S-cell position — a named `S-cell`/`Schrödinger` marker cage.
**ADR-0009** decides what a settled S-cell is *worth* — its two digits combined
into the `s_value` channel a values-distinct reader consumes. **ADR-0010**
extends that value to a doubled S-cell (`2·s_value`) and defaults the `combine`
rule to `sum`. What none of those settle, and this one does, is the mapping from
a mark a setter draws to the working-state directive the decoder emits.

The retired scheme let a cell's center-mark *count* pick the directive (two
marks → pin, one → half, zero → bare) and put the pair's digits on the marks
themselves. It also read a given as possibly the lower digit of an S-cell, and
hard-raised when a marker cell also carried a settled `value`. The new model
moves selection onto the cage `value`, demotes marks to a check, and reads a
settled digit as a flat "not an S-cell."

ISS is no guide — it has no Schrödinger cells (ADR-0009). The authority is
gridfind's own directive model (`puzzle.py`) and the #347 acceptance criteria.

## Decision

A marked Schrödinger cell reads through exactly one of the rows below. The
marker cage supplies "is an S-cell" and, through its `value`, the digits; the
cell's own marks and settled digits only ever *restrict* or *contradict* that,
never select it. The table describes a cell a cage *names*; whether the mode is
on at all is a separate question the next paragraph settles.

**Presence enables the mode; membership pins known S-cells.** A named
`S-cell`/`Schrödinger` block's *presence* enables Schrödinger reasoning, whether
or not it names a single cell: the decoder synthesizes the `schrodinger`
constraint, gives every cell the `is_s` freedom the solver discovers S-cells
with, and defaults the digit domain to `0…N` — the classic `k = 1` extra digit
prepended as `0` below the base `1…N` (an explicit `minDigit` still overrides).
An empty block therefore means "discover them all," leaving the grid's own
arithmetic to force where the S-cells fall; a block that *names* cells
additionally pins those through the table below. So an S-cell may arise where no
cage names it — a doubled cell a killer sum can only close as a doubled S-cell,
for instance. This amends the reading map #342 recorded (its #345 made the cage
the *sole* decode-time S-cell declarer): the cage is still the sole declarer *by
membership*, now joined by *enablement by presence*.

| Marking on the cell | Directive emitted | Meaning |
|---|---|---|
| no marking, but a named `S-cell`/`Schrödinger` block is **present** | none — `is_s` left free | the cell **may** be an S-cell; presence enabled the mode, and the solver discovers whether the arithmetic forces one here. |
| a settled large digit — a **given** (`given:true` + `value`) or a bare **placement** | `SingletonPin(d)` | the cell **is not** an S-cell; its whole value is `d` (`is_s == 0`). The `given`/`placement` wire distinction carries no S-meaning of its own. |
| named `S-cell`/`Schrödinger` marker-cage `value` naming **two** digits (`"a,b"`, or the scalar `"ab"` in a single-character domain) | `SCellPin{a,b}` | the cell **is** an S-cell holding the pair `{a,b}`. |
| marker-cage `value` naming **one** digit (`"a"`) | `HalfSCell(a)` | the cell **is** an S-cell, `a` is one of its two digits, partner unknown. |
| marker-cage `value` **absent, empty, or unparseable** | `BareSCell` | the cell **is** an S-cell, neither digit stated. |
| **center marks on a caged cell** | `SCellMarkRestriction(marks)`, layered on the cage's directive | a consistency check, not a selector — see the restriction rules below. |
| **center marks on an uncaged cell** | ordinary candidates | plain pencil-marks; declare **no** S-status. |
| a marker cell that **also** carries its own settled large digit | both the cage directive **and** `SingletonPin(d)` | the two collide on S-cell-ness (`is_s == 1` vs `0`) → **broke**. Not a decode error. |

**The cage `value` selects; center marks only restrict.** Directive selection
is a property of the cage, read once from its `value`. A caged cell's own center
marks are optional and layer a restriction over whichever directive the cage
chose (`SCellMarkRestriction`), narrowing the cell's two slots to the marked
digits:

- a **pin** `{a,b}` needs the marks to contain the pair (`{a,b} ⊆ marks`); a
  stray extra mark stays **found**, a mark that drops either digit reads
  **broke**;
- a **half** `a` needs the digit marked and at least two marks
  (`a ∈ marks`, `|marks| ≥ 2`);
- a **bare** needs at least two marks, the pair drawn from them (`|marks| ≥ 2`).

A pinned S-cell with no marks stays valid — marks are never required once the
cage `value` fixes the pair. The `≥ 2` floors need no counting: restricting both
slots to a single mark collides with the S-cell's `d0 < d1`, so the solver
alone reports the break. Every restriction violation surfaces as solver
`INFEASIBLE → broke`, never a decode raise.

**A marker cell's own settled digit is a contradiction, not a raise.** A cell in
an `S-cell` marker cage that *also* carries its own given/placement emits both
directives: the marker forces `is_s == 1`, the singleton pin forces
`is_s == 0`. The decoder no longer hard-raises this case; it emits both and lets
the solver report the ordinary infeasibility — **broke** (spec #348, resolving
[#346](https://github.com/caneff/gridfind/issues/346)). This is the one place
this ADR reads differently from #352's drafted acceptance line, which still
called it a "hard error": #348 settled #346 the other way — broke — before this
ADR was written, and `CONTEXT.md` and the decoder already agree.

**Out-of-domain digits stay malformed.** A `value` (or given/placement) that
parses a digit the board never declared is not softened to bare; it rides into
the directive and is refused as **malformed** at verdict, exactly as an
out-of-domain given is (ADR-0009's value rules; the malformed contract in
`CONTEXT.md`). Malformed is a claim about what the puzzle says; broke is a claim
that no completion exists. A well-formed marking whose completion is impossible
is broke, not malformed.

## Cross-references

- **[ADR-0009](0009-cage-distinctness-mode-digit-or-value.md)** — what a settled
  S-cell is *worth*: its two digits combined into `s_value` under the `combine`
  rule, read by any values-distinct consumer through `value_expr`. The table
  above names the position and digits; ADR-0009 names the value they produce.
- **[ADR-0010](0010-doubled-schrodinger-cell-value.md)** — a doubled S-cell is
  worth `2·s_value`, and the puzzle-wide `combine` default is `sum`. A cell can
  carry an `S-cell` marking and a `Doubler` marking at once; its value composes
  through that ADR.
- **[ADR-0012](0012-named-marker-cages-retire-the-color-channel.md)** — which
  channel *declares* the S-cell position: a named `S-cell`/`Schrödinger` marker
  cage, not a color bit. This ADR supersedes that ADR's marker-semantics
  paragraph, where the cell's center-mark count still selected the directive
  (two marks → pin, one → half, zero/3+ → bare); selection now reads the cage
  `value`, and marks only restrict.

## Considered options

- **Leave the model spread across the three tickets' `CONTEXT.md` edits.**
  Rejected: a marking is settled by reading four merged branches together, with
  no one record that says the retired mark-count scheme is gone. The single table
  is the point.
- **Keep #352's "hard error" for a marker cell that also holds a settled
  digit.** Rejected: #348 already resolved #346 as **broke**, and the decode
  raise is deleted in code. An ADR that recorded "hard error" would contradict
  the shipped decoder on day one.

## Consequences

- A reader settles any S-cell marking against one table, and the three behavior
  tickets have a single downstream reference instead of three scattered
  `CONTEXT.md` paragraphs.
- The retired mark-count-selects scheme is on record as retired: selection is a
  cage-`value` property, center marks are a consistency layer, and a settled
  digit is a flat "not an S-cell" — no "lower digit," no "either slot," no
  count-driven fan-out survives in the model.
- ADR-0012 gains a supersession pointer to this ADR for its marker-semantics
  paragraph, the same way ADR-0008 points to ADR-0012 and ADR-0009 points to
  ADR-0010.
