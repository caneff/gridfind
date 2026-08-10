# Diagnosis: the 6×6-from-the-CLI break

Resolves the diagnosis ticket [#169](https://github.com/caneff/gridfind/issues/169)
under the e2e-CLI-suite map [#168](https://github.com/caneff/gridfind/issues/168).
Diagnosis only — the fix is its own effort,
[map #171](https://github.com/caneff/gridfind/issues/171).

## The break

A real 6×6 SudokuMaker link fails through the `gridfind` CLI front door while
the library solves the same puzzle. On current `main`:

```
$ gridfind --schrodinger --reading classic '<6x6 sudokumaker link>'
gridfind: invalid puzzle document: non-classic link: expected 81 cells
```

Exit code is non-zero. It is a clean rejection, not a crash — the CLI refuses a
puzzle the engine can answer.

## Where it goes wrong: decode, and only decode

The failure is entirely in `src/gridfind/sudokumaker.py`. Two things pin the
decoder to a classic 9×9:

- `_reject_non_classic` guards `len(cells) != CELL_COUNT`, and `CELL_COUNT` is
  `BOARD_SIZE * BOARD_SIZE` with `BOARD_SIZE = 9`. A 36-cell 6×6 link trips the
  guard and raises before a `Puzzle` ever exists.
- Behind that guard, `BOARD_SIZE = 9` also fixes the digit domain (`_DIGITS`,
  `_schrodinger_domain`), the cell addressing (`i // BOARD_SIZE`), and the
  classic-regions comparison (`_CLASSIC_REGIONS`, an 81-entry array).

Nothing downstream of decode is at fault. Board sizing, box tiling, and the
witness render all handle non-9 already:

- With `BOARD_SIZE` patched to 6 in a throwaway probe, the same link decodes and
  `verdict()` returns **found**.
- `region_map_for(6)` yields six 3-wide × 2-tall boxes, which match the link's
  own `type 1` regions matrix.
- The witness renders correctly, showing the discovered S-cells as `{a b}`:

```
┌───────────────────────┬───────────────────────┐
│     0       5       3 │     2   {1 6}       4 │
│ {1 4}       6       2 │     3       0       5 │
├───────────────────────┼───────────────────────┤
│     6       4       0 │     5       2   {1 3} │
│     2   {1 3}       5 │     6       4       0 │
├───────────────────────┼───────────────────────┤
│     5       0   {4 6} │     1       3       2 │
│     3       2       1 │ {0 4}       5       6 │
└───────────────────────┴───────────────────────┘
```

## `main(argv, stdin)`

Currently mis-handles the puzzle: it maps the decoder's `ValueError` to a
non-zero exit with the `expected 81 cells` message. Still live on `main`.

## Seed case

A 6×6 Schrödinger link (digits 0–6, one S-cell per house, boxes 3-wide × 2-tall,
two settled clues) with expected verdict **found**. It stays red through the CLI
until the decoder reads board size from the link instead of the `BOARD_SIZE`
constant — the work tracked by map #171.

## Why it's structurally invisible today

The `verdict()`-level corpus (`population_test.py`) drives the library directly,
so it never exercises the decode → CLI → render boundary where this break lives.
That gap is exactly what map #168's e2e suite exists to close.
