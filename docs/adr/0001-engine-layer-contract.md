# ADR-0001: The engine↔layer contract commits to raw OR-Tools

- **Status:** Accepted
- **Date:** 2026-08-06
- **Decides:** [#26](https://github.com/caneff/gridfind/issues/26) (absorbs #18 Q5)

## Context

Layers are gridfind's designed extension point. Every layer — `board`,
`rows-distinct`, `cols-distinct`, `regions-distinct`, `line-count-distinct`, and
every future variant — is written against the seam exposed by `gridfind.engine`.
Changing that seam means editing every layer, so it is worth freezing
deliberately.

The seam a layer actually codes against today is wider than it first looks:

- The **`Layer` protocol** — `name`, `depends_on`, `register(engine)`,
  `emit(engine)` — the [two-phase build](../../CONTEXT.md) every layer
  implements.
- The **`Engine` handle** passed to both phases, and through it:
  - `engine.model` — the raw OR-Tools `CpModel`. Every rule-emitting layer
    pokes constraints straight into it (`add_all_different`, `new_bool_var`,
    `add(...).only_enforce_if(...)`, `add_max_equality`). This is the
    most-used and most load-bearing part of the seam.
  - `engine.structures` / `engine.cells` — read directly (via the `_base`
    helpers `grid_content` / `emit_distinct_count`) to resolve cell addresses
    to their content in phase 2.
  - `engine.add_cell(address, *, low, high, width=1)` and
    `engine.register_structure(name, value)` — the phase-1 write side, called
    only by `board` today.
- Supporting types: `Cell`, `GridfindError`, `MissingDependencyError`.

Every consumer imports these directly from `gridfind.engine`; there is no
re-export. There are **no external or plugin callers** — every layer lives
in-tree ([#24](https://github.com/caneff/gridfind/issues/24) settled this for
the sibling `gridfind.layers` surface, and it holds here too).

## Decision

1. **Raw OR-Tools is the committed contract.** A layer receives an `Engine`
   handle and emits rules against `engine.model` — the OR-Tools `CpModel` —
   directly. We do **not** wrap `CpModel` behind a gridfind facade. The
   two-phase design already confines OR-Tools use to phase 2; a wrapper for
   zero external callers is speculative ceremony.

2. **Layer authors import directly from `gridfind.engine`.** No re-export
   module, no facade — the same import path already in use.

3. **This is a design freeze, not a compatibility freeze.** With no external
   callers there is no backward-compatibility promise to honor. The commitment
   is to the *shape*: the two-phase `register`/`emit` protocol and the `Engine`
   handle are the deliberate design. They may still change — but a change edits
   every layer, so it is made deliberately, not by accident.

4. **`gridfind.engine` will declare `__all__`** naming the seam's vocabulary —
   `Engine`, `Layer`, `Cell`, `build_engine`, `GridfindError`,
   `MissingDependencyError` — mirroring how `gridfind.layers` records its
   surface. Tracked as a follow-up implement ticket.

## When to revisit

Wrap OR-Tools behind a gridfind API only when a concrete trigger appears:

- a second solver is being evaluated (today every layer names OR-Tools methods
  directly, so a swap would edit every layer), or
- a uniform chokepoint over every constraint is needed (logging, naming,
  validation), or
- third-party layer authors appear and should be insulated from OR-Tools'
  own API changes.

None hold today. Until one does, raw OR-Tools is the contract.
