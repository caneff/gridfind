# ADR-0012: named cosmetic cages declare doublers and S-cells; the color channel retires

- **Status:** Accepted
- **Date:** 2026-08-13
- **Decides:** how a SudokuMaker link declares a doubler or an S-cell position —
  which channel carries the mark, how a cosmetic cage's name sorts it, and why
  the color bit and its `--schrodinger`/`--doubler` flags go away
  (spec [#324](https://github.com/caneff/gridfind/issues/324), supersedes parts
  of [ADR-0008](0008-doublers-declared-cosmetic-cages-are-killer-cages.md)).

## Context

A setter declares a doubler or S-cell position in the link itself — gridfind
does not sniff it. ADR-0008 put that declaration on a single cell color: the red
`colors` bit (value 2). Both variants overloaded the *same* bit, so one grid
physically could not encode both — the decoder raised "a link is Schrödinger or
doubler, not both" at variant construction. Which meaning the red bit carried
was not in the link at all; the caller declared it out of band with
`--schrodinger` or `--doubler`. That is brittle, and it forecloses a puzzle that
carries doublers *and* S-cells. ADR-0008 recorded a coexistence path — "the CLI
names which color carries which meaning" — but left it unbuilt as YAGNI.

A verified sample link already uses a different convention. A setter renames a
cosmetic-cage constraint in SudokuMaker, and that name serializes to a top-level
`name` key on the cosmetic (`type 2001`) block. The name is a channel wide enough
to carry the declaration without touching a cell's color.

## Decision

**The declared channel moves off color and onto a named cosmetic cage.** A
setter draws single-cell cosmetic cages over the cells to mark and renames the
constraint. gridfind reads the block's top-level `name` — not `definition.name`,
which is a custom-constraint display field on a different type — and sorts the
cosmetic cage four ways. Matching is against a small recognized set,
case-insensitive and whitespace-trimmed.

| `name` on the block | Behavior |
|---|---|
| absent / empty | no rule — loud stderr warn-drop naming the block ([#435](https://github.com/caneff/gridfind/issues/435)) |
| recognized marker (`Doubler`, `S-cell`, `Schrödinger`) | position marker: emit per-cell directives, **no** `cage`/`group-sum` |
| recognized real-cage label (`Sum`, `Killer`) | honored as a killer cage; the name selects the rule |
| present but unrecognized | no rule — loud stderr warn-drop naming the block, the same policy as absent ([#435](https://github.com/caneff/gridfind/issues/435)) |

**Every name routes through one name → shape registry**
([#431](https://github.com/caneff/gridfind/issues/431)/[#434](https://github.com/caneff/gridfind/issues/434)).
`sudokumaker.naming` holds the single normalized-name → shape table: `Sum`/
`Killer` are a `cage-selector` (needs a cage's cells + value), `Doubler` and
`S-cell`/`Schrödinger` are a `cell-marker` (needs a cage's cells).
`markers.cosmetic_cage_kind` reads a `type 2001` block's name through this
registry; the same registry backs the `type 1000` custom-constraint
carrier-fitness check in `registry._warn_on_dropped_constraints`, so a
cage-shaped name stranded on a payload-less carrier warn-drops there too — one
table, two carriers, one policy.

**Marker semantics.** A `Doubler` block emits one modifier directive
(`is_modifier=True`) per cell and no cage; the cell may still carry a given (a
doubler holds one digit worth twice its value). An `S-cell`/`Schrödinger` block
declares each cell an S-cell, and the cell's *own* center-marks choose the
working-state directive exactly as the red-bit path did (2 marks → S-cell pin
`{a,b}`, 1 mark → half S-cell, 0/3+ → bare S-cell). The marker supplies "is an
S-cell"; the cell supplies the digits, so no S-cell richness is lost.
*(This directive-selection rule is superseded by
[ADR-0014](0014-scell-marking-meaning-model.md): the marker cage's own `value`
now selects the directive, and the cell's center marks only restrict it.)* A marked
cell that also holds a settled `value` is the existing "is-S vs settled
singleton" contradiction and is refused. A marker cage is expected to be
single-cell, but a multi-cell one marks all its cells uniformly.

**The variant is inferred, never declared.** Because the name carries the
declaration, both variants can appear in one grid — a `Doubler` block and an
`S-cell` block side by side. `decode_link` infers the variant from marker
presence: any `S-cell`/`Schrödinger` block turns Schrödinger on (widen the
domain, synthesize the bare `schrodinger` constraint); any `Doubler` block turns
the doubler on (synthesize the bare `doubler` constraint). The color read, the
`LinkVariant` flags, the `--schrodinger`/`--doubler`/`--reading` surface, and the
"not both" guard all retire. Only the classic S-cell reading is built, as before.

**Composition.** A cell may sit in a marker cage and a numeric-sum cosmetic cage
at once; the marker path and the killer-cage path compose over the shared cell.
The sample link shows exactly this — one cell is in the `S-cell` block *and* a
`value: "9"` sum cage. Since an unnamed `type 2001` block carries no rule
([#435](https://github.com/caneff/gridfind/issues/435)), the sum side of this
composition must sit on a `Sum`-named block to survive the policy — the
doubler/S-cell + sum corpus links were migrated onto a named `Sum` cage ahead
of the flip ([#433](https://github.com/caneff/gridfind/issues/433)).

## Considered options

- **Keep color, name the channel at the CLI** (ADR-0008's rejected coexistence
  path). Rejected here in favor of named markers: the declaration belongs in the
  link, not in out-of-band argv. Naming the channel at the CLI still leaves a
  bare color bit whose meaning a caller has to be told, and it never lets one
  grid carry both variants without a second color the setter has to reserve.
- **Sniff the variant from the color bit alone.** Rejected before and still:
  a bare bit is ambiguous, and both variants ride it. The name is unambiguous.
- **Silently strip an unrecognized name and honor the cage as a killer cage.**
  Rejected outright, then and now: a typo'd marker (`Doubbler`) would silently
  compute a verdict under the wrong ruleset — a dropped doubler is an unsound
  verdict.
- **Raise a loud error on an unrecognized name, downgradable via an opt-in
  flag.** ADR-0012's original policy: refuse the whole document by default,
  with `ignore_unknown_named_cages` (CLI `--ignore-unknown-named-cages`) as a
  caller-declared downgrade to strip-and-honor for a setter who knew the label
  was decoration. Retired by [#435](https://github.com/caneff/gridfind/issues/435):
  the raise and the *silent* absent-name path were two different responses to
  the same underlying fact — "this block has no name-selected rule" — and the
  flag was a second knob a caller had to know to reach for.
  **The uniform warn-drop collapses both to one policy: an unnamed cosmetic
  cage carries no rule**, exactly like an unrecognized one, and both say so
  loudly instead of one raising and the other staying silent.
  `registry._warn_on_dropped_constraints` already loud-warns a misplaced name
  on a `type 1000` constraint ([#434](https://github.com/caneff/gridfind/issues/434));
  this makes the `type 2001` carrier consistent with it. No flag remains —
  every caller sees the same behavior.

## Consequences

- ADR-0008's decision 1 stands in spirit — a doubler is a *declared* position —
  but its channel is now a cage name, not a color mark. Its decision 2 (the
  flag-gated color read) and its rejected "CLI names which color" coexistence
  option are superseded by this ADR. ADR-0008 carries a pointer here.
- `decode_link` drops its `variant` parameter; it infers the variant itself, so
  callers (`cli.py`, `witness_validator.py`, the raw-argv `verify_links` /
  `eval_links` scripts) stop constructing a `LinkVariant`. It later drops
  `ignore_unknown_named_cages` too ([#435](https://github.com/caneff/gridfind/issues/435))
  — the uniform warn-drop leaves no refusal for a flag to downgrade.
- Reading a `type 2001` block's name as a semantic channel is surprising without
  this context — this ADR is the why.
