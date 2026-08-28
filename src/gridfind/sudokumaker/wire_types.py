"""The SudokuMaker wire-`type` integer vocabulary: one constant per type
`link_to_puzzle` recognizes, the shared home every per-type decoder and
`registry.DECODER_REGISTRY` import instead of each decoder minting its own
copy and `registry.py` reaching across the boundary to read it. Public
(no leading underscore) as a package-internal seam, not part of the
package's world-facing door (`sudokumaker/__init__.py`'s `__all__`).
"""

from __future__ import annotations

# type 0 is givens: a puzzle's givens are read per-cell (`cells.decode_cell`),
# never off a block, so `DECODER_REGISTRY`'s own `0` row names the type but
# leaves `handler=None` — nothing for the registry's generic dispatch to
# build. `peel_escape_frame` mints a bare `{"type": GIVENS_TYPE}` block for
# its rewritten inner document, mirroring the unconditional rows/cols every
# other classic/jigsaw link gets.
GIVENS_TYPE = 0

# type 1 is the regions block: `{regions: [...]}}`, an `N x N` flat row-major
# matrix of region labels. Present, it decodes to `regions-distinct` — bare
# when the matrix equals the board's own box tiling, or carrying
# `params["regions"]` verbatim for a jigsaw (`regions.regions_constraints`).
# Absent, the puzzle is a Latin square with no boxes. A somedoku puzzle skips
# this type entirely (`decode.link_to_puzzle`) — classic uniqueness is
# incompatible with somedoku's distinct-count target below `N`.
REGIONS_TYPE = 1

# type 200 is white-kropki: `clues: [{value, edge}],
# negative: [...]`, the same wire shape as XV. The type number *is* the
# white/black discriminator — 200 is white/difference, 201 black/ratio — so
# `value` is the target difference, honored verbatim onto the existing
# `pair-difference` layer (a labelled non-1 value is never coerced to 1). A
# non-empty `negative` list is enforced (every listed difference forbidden on
# every unmarked orthogonally-adjacent pair), not dropped — the negative-space
# mechanism in `sudokumaker.edge_clues`.
KROPKI_WHITE_TYPE = 200

# type 201 is black-kropki: the same `clues:
# [{value, edge}], negative: [...]` wire shape as white kropki, `value` read
# as the target integer ratio `k` onto the `pair-ratio` layer (a labelled
# non-2 dot is never coerced to 2). A non-integer `value` raises at decode —
# modeling a wrong verdict would be worse than refusing the link.
KROPKI_BLACK_TYPE = 201

# type 202 is XV: `clues: [{value, edge}], negative:
# [...]`. `value` selects the existing group-sum alias — 10 is X, 5 is V
# — never a raw `sum`, so a puzzle carrying both an XV clue and
# a literal group-sum on the same cells still hits the alias's own
# fixed-param conflict check in `expand_constraints`. A non-empty `negative`
# list is enforced (every listed sum forbidden on every unmarked
# orthogonally-adjacent pair), not dropped — the negative-space mechanism in
# `sudokumaker.edge_clues`.
XV_TYPE = 202

# type 300 is a thermometer block: `slow: bool,
# thermometers: [[cell indices, ordered, bulb first], …]`. Each path becomes
# its own `thermo` Constraint; `slow` rides through onto every path in the
# block. The strict-vs-non-strict split is the `thermo` layer's concern, not
# the decoder's.
THERMO_TYPE = 300

# type 301 is a killer-cage block: `cages: [{cells, value}]`. A
# positive `value` is the killer sum, decoded onto a `group-sum` alongside the
# `cage` (no-repeats) constraint, both over the same cells (ADR-0009) — 0 is
# SudokuMaker's own no-sum cage, decoding to `cage` alone, exactly as `value`
# absent.
CAGE_TYPE = 301

# type 2001 is a cosmetic-cage block: `{cages: [{value: str, cells: [...]}]}`,
# the same nested wire shape as a `type 301` killer block — SudokuMaker's
# decoration tool, not the killer-cage tool (ADR-0008). A numeric string
# `value` graduates a cage to a real killer sum, the only channel an
# out-of-range cage sum (a doubler inside a cage) reaches gridfind through,
# since the killer-cage tool refuses to store one.
COSMETIC_CAGE_TYPE = 2001

# type 100 is even: `{cells: [...], style: {...}}`, the same flat
# raw-indices wire shape a `type 600`/`601` indexing block carries. The type
# number is the even/odd discriminator, exactly like 200/201's white/black
# split. Decodes straight to `parity`, read value mode (`Engine.value_expr`,
# ADR-0009) — a doubled cell's mapped `2·d` is always even, and an S-cell's
# combined `s_value` is judged the same way.
EVEN_TYPE = 100

# type 101 is odd: the same `{cells: [...], style: {...}}` wire shape as
# even, the type number the sole discriminator (100 vs 101). Read value
# mode like even — an odd clue over a doubled cell is therefore
# unsatisfiable (`2·d` is never odd), the deliberate value reading.
ODD_TYPE = 101

# SudokuMaker's global toggles — bare `{type: N}` blocks, one per rule, read
# off real links (the two diagonals also carry a cosmetic `style` gridfind
# ignores). The two diagonals are independent switches: negative is the `\`
# main diagonal, positive the `/` anti-diagonal, so gridfind decodes each to
# its own single-diagonal constraint, never a combined one.
NEGATIVE_DIAGONAL_TYPE = 10
POSITIVE_DIAGONAL_TYPE = 11
ANTI_KING_TYPE = 12
ANTI_KNIGHT_TYPE = 13

# type 14 is disjoint groups: a bare `{type: 14}` toggle, same shape family as
# the four toggles above, but its rule is a distinct-over-groups partition
# (cells at the same position within their region), not a geometric offset —
# `layers.door` builds its own partition from the puzzle's own regions rather
# than dispatching to a fixed one the way `anti-king`/`anti-knight` do.
DISJOINT_GROUPS_TYPE = 14

# type 15 is nonconsecutive: a bare `{type: 15}` toggle, same shape family as
# anti-king/anti-knight — a geometric offset rule, not a partition — so it
# joins them through the same `_global_toggle_handler`. No `difference`
# param on the wire: SudokuMaker fixes the forbidden gap at 1 and does not
# expose it as a setter-configurable value.
NONCONSECUTIVE_TYPE = 15

# type 16 is a global-entropy block: `{groups: [bitmask, …]}`. SudokuMaker
# does not model "global mod" as its own type — both entropy and mod ride
# this one wire block, distinguished only by which digit-bitmask groups
# populate `groups` (docs/research/sudokumaker-global-geometry-wire-format.md
# #4/#5): three bands of three consecutive digits is entropy on a classic
# 9x9, three mod-3 residue classes is mod, a two-group low/high split is
# either preset's shape on a 4x4/6x6/8x8. `groups` rides through onto its own
# `window-groups` Constraint verbatim, never defaulted — a block missing it
# surfaces the gap here as `KeyError`, the same bare-subscript posture
# `grouped_constraints` takes for its own `groups` (`GROUPED_TYPE`). A link
# enabling two blocks (entropy plus mod together) decodes to two
# `window-groups` Constraints, both enforced (`layers/window_groups.py`).
GLOBAL_ENTROPY_TYPE = 16

# type 1000 is a custom constraint: `{definition: {name, ...}, input: {...}}`,
# SudokuMaker's programmable-logic block. gridfind never interprets the
# programmed logic itself — it recognizes a `type 1000` block only by its
# declared `definition.name` (`dropped.constraint_name`), the same
# name-only reading a `type 2001` cosmetic cage's top-level `name` gets
# (`naming.named_component`).
CUSTOM_CONSTRAINT_TYPE = 1000

# type 305 is a windoku-style extra region: `{cells: [...]}`, the same flat
# raw-indices wire shape a `type 600`/`601` indexing block carries — one
# block per drawn window, no nested `cages`/`value` the way a killer cage
# carries. Decodes straight to `extra-region`, honored by reusing the
# existing `DistinctOverGroups` layer with the named cells as one more group
# in its partition (a puzzle drawing several windows carries several `type
# 305` blocks, folded together at `layers.door`).
EXTRA_REGION_TYPE = 305

# type 302 is a clone block: `{groups: [[cell indices], …], style: {...}}` —
# a flat, top-level `groups` list, no `input` wrapper and no nested `{cells:
# [...]}` object (`links/found-clone-4x4-human.txt`, wire payload
# `{groups: [[0, 14], [1, 15]]}`). Each group stands alone, its own cells
# held to an equal digit *set* — digits only, never the modifier marking (a
# cloned cell does not inherit its source's doubler/constant) — read digit
# mode through `Engine.real_digit_slots` (ADR-0019 dec 4/6) so the sentinel
# filling a singleton's second slot is never compared. A block's several
# groups carry no relationship to one another: equal digits within each
# group, never across them.
CLONE_TYPE = 302

# type 303 is a quadruple-clue block: `{clues: [{corner, digits}]}`. Each
# `corner` names a 2x2 block (`quadruple.corner_to_quad`); each of its
# `digits` must equal at least one of those four cells' values
# (`Engine.value_expr`, ADR-0009) — `2·d` over a doubler, combined `s_value`
# over an S-cell, the bare digit otherwise — read value mode like even/odd.
QUADRUPLE_TYPE = 303

# type 400 is a renban line: `{lines: [[cell indices, ordered], …]}`. Each
# path becomes its own `line` Constraint carrying `relation: "renban"` and
# the path's addresses — no extra block param; renban's distinctness-and-span
# rule needs nothing beyond the path. This is the first **digit-mode**
# relation of the nine-relation line-clue family (spec #672): the `Line`
# layer reads it through `Engine.real_digit_slots` rather than `value_expr`,
# so a Schrödinger cell on the line contributes both its digits to the run.
RENBAN_TYPE = 400

# type 401 is a whisper line: `{lines: [[cell indices, ordered], …],
# minDifference: int}`. Each path becomes its own `line` Constraint carrying
# `relation: "whisper"` and the path's addresses; `minDifference` (German 5,
# Dutch 4, or any setter-chosen threshold) rides through onto every path in
# the block, read at the `Line` layer, not defaulted here — a block missing
# it is a malformed whisper clue, not a "no minimum" one. This is the first
# wire type of the nine-relation line-clue family (spec #672); every other
# relation (renban 400, palindrome 402, between 403, region-sum 404, sequence
# 405, grouped-line 406, lockout 407, double-arrow 409) shares the same
# `lines`-path wire shape and decodes to the same `Constraint("line", ...)`
# shape through its own `DECODER_REGISTRY` row.
WHISPER_TYPE = 401

# type 402 is a palindrome line: `{lines: [[cell indices, ordered], …]}`. Each
# path becomes its own `line` Constraint carrying `relation: "palindrome"` and
# the path's addresses — no extra block param; palindrome's mirror-pair rule
# needs nothing beyond the path. This is the second digit-mode relation of the
# nine-relation line-clue family (spec #672), and the first
# **position-structured** one: unlike renban's set-structured pooling, a
# Schrödinger-widened cell on the path has no defined mirror-pair fold, so the
# `Line` layer refuses loud rather than guess one.
PALINDROME_TYPE = 402

# type 403 is a between-line: `{lines: [[cell indices, ordered], …]}`. Each
# path becomes its own `line` Constraint carrying `relation: "between"` and
# the path's addresses — no extra block param; the two path ends are the
# bulbs, read at the `Line` layer through `value_expr`, and every interior
# cell must sit strictly between them. This is the second **value-mode**
# relation of the nine-relation line-clue family (spec #672), after whisper:
# a doubler or Schrödinger cell at either bulb or on an interior cell counts
# as its folded value, the same seam whisper reads through.
BETWEEN_TYPE = 403

# type 405 is a sequence line: `{lines: [[cell indices, ordered], …]}`. Each
# path becomes its own `line` Constraint carrying `relation: "sequence"` and
# the path's addresses — no extra block param. Value-mode: every successive
# `value_expr` difference along the path must be equal, any integer
# including 0, so a doubler or Schrödinger cell counts as its folded value.
# `links/found-sequence-flat-9x9.txt` is a real captured 405 link whose
# line holds 5-5-5 as entered digits: SudokuMaker builds and shares a flat
# line, so the predicate asserts no distinctness. The solver-side witness
# for that reading is `layers/line_test.py::test_a_flat_sequence_line_is_valid`.
SEQUENCE_TYPE = 405

# type 406 is a grouped line (entropic / modular / parity): `{lines: [[cell
# indices, ordered], …], groups: [bitmask, …]}`. Each path becomes its own
# `line` Constraint carrying `relation: "grouped"` and the path's addresses;
# `groups` rides through onto every path in the block verbatim, read at the
# `Line` layer, not defaulted here — a block missing it is a malformed
# grouped-line clue, not a "no groups" one. The third digit-mode relation of
# the nine-relation line-clue family (spec #672), and — like palindrome — a
# position/window-structured one: a Schrödinger-widened path cell has no
# defined single-window fold, so the `Line` layer refuses loud through the
# same `sole`-backed raise palindrome stood up, rather than guess one. No real
# `type 406` link was available to ground-truth the wire shape (the same gap
# clone's `type 302` and quadruple's `corner_to_quad` document); `groups` is
# taken to already be a list of digit bitmasks on the wire — SudokuMaker's own
# bitmask convention for a digit set (`sudokumaker.cells._write_s_cell`'s
# `candidates` field) — a one-function swap in `grouped_constraints` if a real
# link corrects it.
GROUPED_TYPE = 406

# type 407 is a lockout line: `{lines: [[cell indices, ordered], …]}`. Each
# path becomes its own `line` Constraint carrying `relation: "lockout"` and
# the path's addresses — no extra block param; the two path ends are the
# bulbs, read at the `Line` layer through `value_expr`, exactly like between.
# The fourth **value-mode** relation of the nine-relation line-clue family
# (spec #672), and between's inverse: the bulbs must differ by at least
# `size // 2` (computed from `engine.board.size`, never read off the
# wire — 9x9 = 4, 6x6 = 3, 4x4 = 2), and every interior cell's value must
# sit strictly *outside* the closed bulb interval, never equal to either
# end. Threshold ratified from spec and amended from a real 4x4 SudokuMaker
# link, ADR-0021.
LOCKOUT_TYPE = 407

# type 404 is a region-sum line: `{lines: [[cell indices, ordered], …],
# singleRegionTotals: bool}`. Each path becomes its own `line` Constraint
# carrying `relation: "region-sum"`, the path's addresses, and the block's
# own `singleRegionTotals` — defaulted to `False` when the wire omits it,
# unlike whisper's `minDifference` or grouped's `groups`, since the spec
# itself names `False` the default meaning, not an absent-knob gap. The
# sixth **value-mode** relation of the nine-relation line-clue family (spec
# #672), and the family's one **cross-relation** seam: at the `Line` layer it
# reaches past its own params into the region door
# (`region_map_for_constraints`, `layers/regions.py`) to resolve the board's
# partition, segments the path per-visit against it, and asserts equal
# segment sums. `singleRegionTotals = True` names per-region pooling, which
# gridfind does not model, so the `Line` layer raises rather than guess a
# rule; `False` is per-visit segmentation, ratified from spec without a
# captured real link (ADR-0023).
REGION_SUM_TYPE = 404

# type 408 is an arrow: `{bulbsWithArrows: [{bulbCells: [ids], arrows:
# [[ids], ...]}, ...]}` — not a line-clue-family type, and not a toggle: a
# top-level list of bulb entries, each naming its own bulb cell(s) and one or
# more independent shaft paths. Wire shape ratified from #760's charting
# session against SudokuMaker's live bundle (formatVersion 1.6.0,
# 2026-08-27), the same source #748's research doc used. Each entry decodes
# to one `arrow` Constraint carrying `bulb` and `arrows` (addresses, wire
# order preserved) for the `Arrow` layer: every shaft's cells must sum
# (value_expr) to the bulb's own value, each shaft independently, digits free
# to repeat along a shaft. A single-cell bulb reads its value directly; a
# multi-cell bulb (a pill, read as a place-value number) is #761's declared
# out-of-scope follow-up (#762) — the `Arrow` layer refuses one loud rather
# than read it wrong.
ARROW_TYPE = 408

# type 409 is a double-arrow line: `{lines: [[cell indices, ordered], …]}`.
# Each path becomes its own `line` Constraint carrying `relation:
# "double-arrow"` and the path's addresses — no extra block param; the two
# path ends are the bulbs, read at the `Line` layer through `value_expr`,
# exactly like between and lockout. The fifth **value-mode** relation of the
# nine-relation line-clue family (spec #672): the interior cells' values must
# sum to the two bulbs' own sum, reversal-invariant, a 2-cell path (no
# interior) naturally broke rather than a special-cased pass. A double-arrow
# is visually near-identical to a between-line (403) — both draw circles at
# both ends — but the decoder tells them apart by wire type alone, never a
# glyph. That 409 is the double-arrow (not, say, another between variant) is
# ratified from #670's research and the synthesized corpus, not a captured
# real link (ADR-0022) — a one-constant swap here if a real link corrects it.
DOUBLE_ARROW_TYPE = 409

# type 600 / 601 are the 159 indexing clue's two axes: `{cells: [...],
# style: {...}}`, the same flat raw-indices wire shape a marker cage carries.
# The type number is the row-vs-column discriminator, exactly like 200/201's
# white/black split. gridfind owns this wire type — no
# research ticket — so unlike 200/201 the split below is a build-time choice,
# not read off a real SudokuMaker link carrying both — the model does not
# hinge on which is which (a future real link proving the assignment
# backwards is a decode-detail swap, not a rebuild).
INDEXING_ROW_TYPE = 600
INDEXING_COL_TYPE = 601
