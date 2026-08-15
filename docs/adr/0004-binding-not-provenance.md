# ADR-0004: the channel test is binding, not provenance — `CellGeometry` holds the board's fixed facts

- **Status:** Accepted
- **Date:** 2026-08-09
- **Supersedes:** [ADR-0003](0003-two-channels-registry-and-engine.md)
- **Decides:** what shape the **structure registry**'s read side takes, now that
  ADR-0003's revisit condition has fired (wayfinder map
  [#43](https://github.com/caneff/gridfind/issues/43), ticket
  [#110](https://github.com/caneff/gridfind/issues/110), sweep
  [#109](https://github.com/caneff/gridfind/issues/109)).
- **Amended:** 2026-08-15 — the descriptor is built (ticket
  [#420](https://github.com/caneff/gridfind/issues/420)) and the adjacency slot
  is locked, not yet built: a directional stepper, resolved against the cell
  space (sub-map [#398](https://github.com/caneff/gridfind/issues/398), spec
  [#416](https://github.com/caneff/gridfind/issues/416)). See "The directional
  stepper" under Decision.

## Context

ADR-0003 said to revisit if a non-layer consumer of a *derived* fact appeared,
and predicted the fix would be "a registry read handle." The sweep (#109) found
the consumer: `verdict.py:88` casts `engine.structures["grid"]` to read the grid
of `RxCy` addresses that `layers/board.py:45` registers, and `cli.py:88` gets
the same grid one hop later as a copy on the **witness**.

The read handle is the wrong fix, because the diagnosis was wrong. ADR-0003
sorted every fact by **who produced it** — the setter, or a **layer**. The
address grid answers neither. `board.py` builds it from `board.size` alone:

```python
grid = [
    [cell_address(row, col) for col in range(1, board.size + 1)]
    for row in range(1, board.size + 1)
]
```

No layer's work informs it. Any code holding the board could compute the
identical list. Provenance files it under "derived" and sends it to a channel
only layers read, so a non-layer had to cast its way in.

**Provenance was standing in for something else.** The registry exists (decision
9) so layers need not import each other: the `regions` layer asks for the name
`"grid"` and never meets `board.py`. That late binding costs real money —
`engine.structures` is `dict[str, object]`, so every read pays a cast, no reader
can be sure the name is registered, and a phase-1 read may find nothing. You pay
that price when producer and consumer **must stay apart**. A cell's **content**
is such a fact: a Schrödinger layer widens it in phase 1, and `regions` must not
know that layer exists. The board's size is not: the setter typed it, no layer
changes it, and every reader wants it typed back.

ISS ran this experiment and drew the line correctly. Its `CellGeometry` holds
`makeCellId`/`parseCellId` (the `R1C1` codec), `minValue`/`maxValue`/`allValues`,
`boxDimsForSize`, and `cellGraph()` — and **no handler produces any of it**.
`CellGeometry.fromShapeSpec(spec)` builds the whole descriptor at parse time and
the engine hands it to each handler at `initialize`; the parser, the constraint
model, and the renderer read the same object. Handlers affect each other only by
pruning candidates in shared grid state, where no producer is ever named. ISS has
no registry, and never needs to ask who produced what
(`docs/reference/iss-design-decisions.md` §2.2).

## Decision

1. **The test is binding, not provenance.** Must the producer and the consumer
   stay apart? Yes → the **structure registry**. No → a typed field anyone can
   read. Provenance remains the explanation for why the two usually coincide; it
   is no longer the rule.

2. **`CellGeometry` is the typed home for the board's fixed facts** — the board
   size, the digit values, the box tiling, and the grid of `RxCy` addresses. It
   is metadata only: no content, no solver state.

3. **A free function builds it from a `Board`; `build_engine` puts it on the
   engine.** Layers read it off the engine. `sudokumaker.py`, which has no
   engine, builds its own from the board it already holds instead of keeping
   `BOARD_SIZE = 9`.

4. **The `board` layer stops registering `"grid"`.** `grid_content` reads the
   addresses off `CellGeometry` and drops its cast; `verdict.py:88` does the
   same. The registry keeps only what layers genuinely make.

5. **ADR-0003's rule 3 is retired.** "A new carried field must earn it" was
   written in provenance terms. The setter's `constraints` and `board` stay
   carried fields — they are setter input, fixed before any layer runs, and
   nothing must stay apart.

6. **The directional stepper is `CellGeometry`'s one adjacency primitive,
   locked but not yet built.** Given a start cell address and a direction
   `(Δrow, Δcol)`, `step` returns the cell address at that offset, or nothing
   when no cell is declared there; `walk` returns the ordered tuple of cell
   addresses from the start in that direction until the line leaves the cell
   space. One primitive serves every cell-to-cell clue foreseeable today —
   anti-knight and anti-king apply it once per offset, an outside-clue line
   walks it whole — so `CellGeometry` never learns a variant name; each clue
   owns its own offset list. **vs ISS:** shape matches `CellGraph.traverse`,
   which `walk` iterates. **One knowing deviation:** ISS's `traverse` clips to
   the grid rectangle (`numRows`/`numCols`); the stepper resolves against the
   **declared cell-address set** instead, returning nothing only when no cell
   sits at the target. Off-grid solved cells are coming (sub-map
   [#399](https://github.com/caneff/gridfind/issues/399)) and `CellGeometry` was
   named over `GridGeometry` for exactly this (see Consequences below) —
   clipping to the rectangle would force #399 to reopen the stepper; resolving
   against the space does not. The deviation costs nothing today: with only
   grid cells declared, cell-space membership equals the rectangle bound.
   Locked in spec [#416](https://github.com/caneff/gridfind/issues/416); ships
   in a later ticket of that spec, not this ADR's own extraction (#420).

## Considered options

- **A registry read handle** (ADR-0003's own prediction). Rejected: it gives
  `verdict` a polite way to read a fact it could compute itself, leaves the grid
  in a channel it never belonged in, and adds a thing to maintain.
- **A `_geometry` helper module** deriving facts on demand, this issue's earlier
  lean. Rejected as a *complete* answer — it is half of decision 3, but on its
  own it leaves `"grid"` registered and the cast alive. The free function
  survives; the registry entry does not.
- **Do nothing** — keep handing consumers copies, as #105 gives the box shape to
  the witness. Rejected: the copies exist because no legal typed home existed.
  Once one exists, they are duplication with no argument for it.

## Consequences

- **This supersedes [#104](https://github.com/caneff/gridfind/issues/104)**,
  which types the `"grid"` registry entry rather than removing it. Land, narrow,
  or close it deliberately — do not let it land by momentum.
- **#105's box-shape copy on the witness** becomes a `CellGeometry` read.
- **The digit values do not move channels.** They stay setter input on the
  carried field; `CellGeometry` becomes the surface readers ask, so `board.py`,
  `emit_distinct_count`, and `Engine.restrict` stop reaching two dots into the
  setter's descriptor. Stated here so a later reader does not think we forgot
  them.
- **Adjacency has a slot, and now a locked design.** ISS puts `cellGraph()`
  inside the same descriptor; decision 6 records `CellGeometry`'s own
  directional stepper and its one knowing deviation from ISS. The stepper
  itself, and the anti-knight/anti-king/X-sudoku clues that prove it, ship in
  a later ticket — this ADR only records the design spec #416 locked.
- **The name defends itself in the docstring.** gridfind has a real `Cell` class
  (`engine.py:55`), which ISS does not, so `CellGeometry` can be misread as the
  geometry of one cell. It is the geometry of the puzzle's cell **space**. The
  name beats `GridGeometry` because cells outside the grid are coming, and
  "grid" would then name a subset — the same reason ISS chose "cell" for a
  descriptor that spans grid cells and var cells.
- **Hex and non-square boards stay out of scope.** Nothing here forecloses
  either, and nothing here builds for them.

## When to revisit

Revisit if a board layer builds a grid that depends on **more than the board** —
something decided at run time rather than fixed by the setter's declaration.
Such a grid fails the binding test: its producer and its consumers must stay
apart, so it belongs in the registry, and the question of who may read it
returns with it.
