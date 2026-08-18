# ADR-0019: a constraint reads an S-cell or modifier cell per its declared mode — digit or value

- **Status:** Accepted
- **Date:** 2026-08-18
- **Decides:** how a gridfind constraint declares whether it reads a widened
  **S-cell** as its individual digits or its combined value, and a
  **modifier** cell as its underlying digit or its mapped value — where the
  choice lives, the digit-mode semantics over two digits, the fate of the
  `s_blind` refusal, and the engine seam a layer calls. Records the model
  charted on the [S-cell / modifier reading-model
  map](https://github.com/caneff/gridfind/issues/592) across tickets #593–#596.
  Supersedes parts of [ADR-0009](0009-cage-distinctness-mode-digit-or-value.md).

## Context

Once a cell can hold more than one digit or be worth more than its face value,
"what a constraint reads" splits. A **Schrödinger cell** (S-cell) widens a cell
to two digits at once; a **modifier** (a doubler, a constant) remaps a cell's
value. So a constraint over such a cell must know two things: does it read the
cell's **digit(s)** or its **value**, and — for an S-cell in digit mode — does
its property apply to each digit, any digit, or the digit set?

S-cell-ness is gridfind's own addition. SudokuMaker knows nothing of S-cells: a
link stores an opaque cosmetic-cage **name** string, and gridfind's convention
rides in that name. So the reading model lives entirely in gridfind's
representation, and any per-puzzle choice a setter makes reaches gridfind only
through that name channel, never through an SM feature.

[ADR-0009](0009-cage-distinctness-mode-digit-or-value.md) answered a slice of
this for the cage (its `distinct-over: digit | value` mode) and set a default —
a constraint reads *value* unless its meaning fixes *digit*. This ADR
generalizes that slice into the whole model and corrects two of its calls.

## Decision

**1. The reading is intrinsic to the constraint type; a declared param appears
only where the constraint is genuinely two-valued.** Most constraints have one
correct reading fixed by their meaning: a thermo and a group-sum read value, the
classic killer no-repeats reads digit. That reading lives in code, not in a
knob. The one exception today is the cage's `distinct-over: digit | value`,
because "distinct" really does mean two different things. A **global
puzzle-wide** reading mode is rejected: one puzzle can hold a digit-mode cage
and a value-mode thermo at once, so no single switch expresses it.

**2. Reading has two independent knobs, giving four corners.** The **modifier
reading** knob is `underlying | mapped`; the **S-cell reading** knob is
`per-digit | combined`. The engine exposes each corner as its own seam method:

| modifier | S-cell | seam |
|---|---|---|
| underlying | combined | `base_value` |
| mapped | combined | `value_expr` |
| underlying | per-digit | `real_digit_slots` |
| mapped | per-digit | **refused** |

The fourth corner — a mapped value read digit-by-digit — has no definition: a
doubled S-cell is worth twice its *combined* value
([ADR-0010](0010-doubled-schrodinger-cell-value.md)), not a per-digit map. A
read that lands there raises rather than guess. It becomes definable only when a
real clue needs it.

**3. An S-cell's value is the setter's per-puzzle combine mode, carried in the
link's cosmetic-cage name.** The value of a widened S-cell is not a rule
gridfind owns; the setter defines it, and different puzzles define it
differently. The setter picks a **combine mode** from a fixed menu — `sum` (two
digits add) or `concat` (they juxtapose, so 2 and 3 make 23) — and that choice
rides the link as a word on the S-cell's cosmetic-cage name, exactly as
`Constant N` rides a name. gridfind decodes it; SudokuMaker only transports the
string. A bare `S-cell` name defaults to `sum`; `S-cell concat` selects concat;
an unknown word raises. This **supersedes ADR-0009 decision 4** (which held the
combine mode as a gridfind-owned default) and relaxes **decision 7** (the
reading declaration is no longer wire-invisible — the combine mode rides the
name).

**4. Digit-mode semantics over two digits: the clue owns its quantifier; the
engine owns one gating invariant.** In digit mode a constraint faces up to two
digits, and no single quantifier fits every clue — even/odd applies to **each**
digit (∀), quadruple-presence to **any** (∃), clone to the whole **set**,
digits-distinct to **set membership**. So the quantifier is the clue's, not a
global rule. The engine's one uniform contribution is **real-digits-only
gating**: a digit-mode read ranges over `d0` always and `d1` only when the cell
is a real S-cell (`is_s`), so the sentinel that fills a singleton's second slot
is never a live term. A width-1 cell is simply the one-real-digit case. Because
`d0 < d1` is strict, an S-cell always holds two **distinct** digits — never a
multiset — and the read is an unordered **set**: `d0`/`d1` order is
canonicalization, not meaning, so a clone or any order-sensitive clue compares
digit sets.

**5. The `s_blind` flag and its refusal retire.** `s_blind` marked a layer that
reads a bare single slot and so had no defined meaning over a widening layer.
Under decisions 1–4 every reading is now one of two S-aware modes, so nothing
genuinely lacks a defined meaning over an S-cell; `s_blind` is transitional, not
a permanent capability. Every layer declares a mode — value or digit — and the
flag, the compose-time refusal `refuse_s_blind_over_widening`, and `s_blind.py`
become dead code. Until the last holdout (`thermo`, `offset_adjacency`)
declares its mode, the refusal stays **unchanged** as a transitional guard: a
still-mode-less layer over a widening layer is still refused. The deletion is
executed on issue #523, whose goal this broadens from "every layer reads
`value_expr`" to "every layer declares a mode (value or digit)" — so a
digit-mode lift retires the flag just as a value-mode lift does.

**6. The engine seam is explicit per-mode calls, not a unified dispatcher.**
Value mode returns one expression; digit mode returns a gated slot list — two
different shapes, so a unified `read(address, mode)` would hand back a union the
caller must destructure and the type checker cannot police. The layer knows its
mode in code (decision 1), so it calls the matching method; the cage's
`distinct-over` param picks between two explicit calls, as it does today. Digit
mode gains one new read: `real_digit_slots(address)` returns each real digit
paired with its guard — `None` for `d0`, `is_s` for `d1` — and the clue builds
its rule with `.only_enforce_if(guard)` on the gated term. The raw `contents`
primitive stays, and **digits-distinct keeps reading it**: its
`add_all_different` tolerates the sentinel, which never collides, so it needs no
gating. `real_digit_slots` serves the predicate-shaped clues that cannot see the
sentinel.

## Considered options

- **A unified `read(address, mode)`.** Rejected: value mode and digit mode
  return different shapes (one expression versus a gated slot list), so the
  return type would be a union the caller destructures and the type checker
  cannot help with. Explicit per-mode calls stay typed and let the layer's own
  code state which mode it means.

- **`s_blind` as a permanent per-constraint capability** ("value-only" /
  "digit-only"). Rejected: a layer's intrinsic mode already *is* its
  declaration, and nothing asks a digit-mode layer to also do value mode. There
  is no capability left to advertise, and no constraint genuinely resists both
  modes.

- **A single uniform digit-mode quantifier.** Rejected: even/odd (∀),
  presence (∃), clone (set-equality), and distinct (set-membership) do not
  reduce to one rule, and a fixed quantifier menu in the engine would miss the
  set-shaped clues, which would bypass it anyway.

- **Combine mode as a gridfind default** (ADR-0009 decision 4). Rejected here:
  the value of an S-cell is the setter's per-puzzle choice, so the mode rides
  the link, not a gridfind constant.

## Consequences

- The reading model is settled; the build has ticket homes and this ADR is the
  reference each reads against. Issue #523 builds `real_digit_slots`, lifts the
  holdouts (`thermo` to value, `offset_adjacency` to digit), and deletes the
  `s_blind` machinery. The four cell-property clues (issue #408) each declare
  their own digit-mode quantifier against decision 4. Thermo on the value seam
  is issue #590; the `concat` combine build is issue #535.
- ADR-0009 keeps decisions 1–3 and 5–7; its decision 4 (combine as a
  gridfind-owned default) is superseded by decision 3 here, and its decision 7
  is relaxed — the combine mode now reaches gridfind through the cosmetic-cage
  name.
- A reader adding a constraint picks a mode by the constraint's meaning, calls
  the matching seam method, and — in digit mode — supplies only the predicate,
  since the engine handles the real-digit gating.
