# ADR-0020: outside cells — off-grid addressing and registration model

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decides:** how gridfind addresses and registers **outside cells** — the
  positions on the border ring around the grid that outside clues attach to.
  Covers the wire format, the address scheme, who creates a solved outside
  cell, the domain it holds, and whether it prints in the witness. Records the
  model charted on the [outside-cells grilling
  ticket](https://github.com/caneff/gridfind/issues/399). The clue families
  that sit on this plumbing — [arrows #402](https://github.com/caneff/gridfind/issues/402),
  [scalar outside clues #403](https://github.com/caneff/gridfind/issues/403),
  and [escape-the-grid #404](https://github.com/caneff/gridfind/issues/404) —
  are follow-on and were blocked on this decision.

## Context

An outside clue attaches to a row or column from beyond the grid: an X-sum on
the top of a column, a skyscraper on the left of a row, a little-killer on a
corner diagonal. To model any of them, gridfind first needs a way to name the
border position the clue sits on, and — for the one family whose off-grid
cells the solver fills — a way to create those cells in the engine.

Two facts were ground-truthed while charting and are settled input here, not
decisions:

- **Wire format** (from two real ChinStrap links): outside clues are types
  **500–504**, each `{clues: [{value, outerCell, [diagonal]}], style}`. Type
  `500` carries `diagonal` (little-killer). `value` is the clue's scalar;
  `outerCell` is the border position.
- **`outerCell` geometry:** `outerCell = row·(N+2) + col` on an (N+2)×(N+2)
  padded board. The grid interior is rows and cols `1..N`; the border ring is
  any position with row or col in `{0, N+1}`. Top edge is row 0, right edge is
  col N+1, bottom is row N+1, left is col 0; the four corners are unused. A
  border position never collides with a grid cell `R1C1..RNCN`. For N=9:
  top-of-c1 is `outerCell 1`, left-of-r4 is `44`, right-of-r9 is `109`.

One split frames every decision below. A **scalar** outside clue — X-sum,
sandwich, skyscraper, numbered rooms — reads a **given** value the setter
writes, and creates **no** solver cell; gridfind uses the given to constrain
the *grid* cells. A **solved** outside cell — one the solver fills — belongs to
**escape-the-grid alone**, where the solver fills off-grid cells and ordinary
clues (dots, XV, lines) decorate them. So the only outside cells the engine
ever creates are escape-the-grid's off-grid cells; the scalar families create
none.

## Decision

**1. An outside cell's address is the padded coordinate, in the same `RxCy`
namespace as a grid cell.** Decode `outerCell` to `(row, col)` on the (N+2)×(N+2)
board and format it as `RxCy` unchanged: `R0C1` is the top of column 1, `R4C0`
the left of row 4, `R10C5` the bottom (N=9), `R5C10` the right. No separate
namespace. The grid uses `1..N`, so a border index of `0` or `N+1` never
collides with a real cell, and `format_address` / `parse_address` already
accept it — `parse_address("R0C1")` returns `(0, 1)` today. The stepper
(`CellGeometry.step`) resolves cells by membership in the declared address set,
not by a `1..N` bounds check, so a declared border cell is reachable with no
change. One address type covers grid and border alike.

**2. A dedicated `outside-cells` layer creates the solved outside cells; no
other place does.** Cell creation has exactly one home today — the `board`
layer, in the two-phase build (`build_engine`). Escape-the-grid's off-grid
cells get a second such home: an `outside-cells` layer, seeded into the stack
when escape-the-grid clues are present, that reads the border addresses its
clues reference and calls `Engine.add_cell` for each **once**. The decoration
clue layers (dots, lines on those cells) `depend_on` this layer and only
**read** the cells. Decoders stay cell-free, as they are now — they emit a
`Puzzle`, never touch the engine.

The one-creator rule is not tidiness; it guards a silent-corruption hazard.
`add_cell` does `self.cells[address] = cell`, so a second `add_cell` for the
same address **replaces** the `Cell` with fresh CP-SAT variables and orphans
any rule that already captured the first — the model keeps the old variable,
the cell dict drops it, and the verdict goes wrong with nothing red to show it.
Two ordinary clues can decorate the same off-grid cell (a dot and a line
crossing it), so per-clue creation would hit exactly this. One creator, and
the decoration layers read a stable cell.

**3. A solved outside cell holds `1..N`, like a grid digit.** Escape-the-grid's
off-grid cells are ordinary digit cells, so their domain is `board.values`,
the same range the grid holds — one formula, no per-clue variation. The
**given** scalar clues carry a clue-defined range too (an X-sum total runs up
to the row sum `N·(N+1)/2`, a skyscraper count caps at `N`), but that range is
a **validation bound on the given value**, checked by the scalar-clue family
(#403) — it is never a solver-cell domain, so it does not enter this model.
Because two clue types on one board only ever validate their own givens against
their own ranges, mixed types never collide.

`add_cell` already takes `low` / `high`, so the seam needs no change. A solved
outside cell is added with `low=board.values.start, high=board.values[-1]`. It
must **not** pass through `Engine.restrict`'s `board.values` guard the way a
grid cell does only because its domain equals `board.values` here anyway; the
guard stays a grid-cell step. The clue-defined range is recorded here only to
place it — it lives with #403, not with cell creation.

**4. A solved outside cell prints in the witness.** The standing invariant is
that the printed witness is independently checkable
([ADR-0015](0015-witness-identity-is-the-full-assignment.md)): a solved value
the reader cannot see breaks that. `Witness.render` today iterates
`CellGeometry.grid` and prints only cells inside the N×N rectangle, walling and
region-mapping against `n×n`. Escape-the-grid extends `render` to draw the
border ring around the grid, so every solved outside cell shows. This is the
one place the strict-N×N rendering assumption has to give.

## Considered options

- **A separate namespace for outside addresses.** Rejected: the padded `RxCy`
  coordinate is collision-free, and the parser, formatter, and stepper already
  accept it. A second namespace adds an addressing home for no gain.

- **Escape-the-grid's decoder creates the outside cells.** Rejected: decoders
  produce a `Puzzle` and never touch the engine, and moving cell creation into
  a decoder splits it across two kinds of home. A layer keeps creation in the
  two-phase build beside `board`.

- **Each decoration clue layer creates the cells it references.** Rejected on
  the orphan hazard above — two clues on a shared off-grid cell silently drop
  the earlier rule's variable. Validated with a throwaway prototype against the
  real engine (issue #399): the shared-cell case orphaned the first clue's
  rule, the one-creator case did not.

- **A clue-defined domain on the solved cell.** Rejected: it only made sense
  under a *solved-scalar* reading gridfind is not doing. The scalar clue's
  value is a **given**, so its range is a validation bound, and the solved
  cell (escape-the-grid) is a plain digit — `1..N`, one formula, no mixed-type
  conflict to design around.

## Consequences

- The plumbing is settled; the three blocked clue families can proceed.
  Escape-the-grid (#404) owns the `outside-cells` layer, the `1..N` domain, and
  the witness-render extension. Scalar outside clues (#403) own the
  clue-defined validation bound on the given. Arrows (#402) sit on the shared
  address model.
- Cell creation now has two homes — `board` and `outside-cells` — both layers
  in the two-phase build. That is the one-home-per-behavior rule read at the
  right grain: each layer is the sole creator of *its* cells, and no decoration
  layer creates any.
- A reader modeling a new outside clue decodes `outerCell` with the formula
  above, names the position in `RxCy`, and — only if the solver fills the cell
  — registers it through the `outside-cells` layer. A given-value clue registers
  no cell at all.
