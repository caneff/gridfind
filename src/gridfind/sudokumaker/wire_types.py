"""The SudokuMaker wire-`type` integer vocabulary: one constant per type
`link_to_puzzle` recognizes, the shared home every per-type decoder and
`registry.DECODER_REGISTRY` import instead of each decoder minting its own
copy and `registry.py` reaching across the boundary to read it. Public
(no leading underscore) as a package-internal seam, not part of the
package's world-facing door (`sudokumaker/__init__.py`'s `__all__`).
"""

from __future__ import annotations

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

# type 302 is a clone block: `{input: {groups: [{cells: [...]}]}}` — the
# nested `input.groups` wire shape SudokuMaker's custom-constraint tool writes,
# the same shape `dropped.has_live_data` already reads to tell a populated clone
# block from an inert one. Each group's cells must hold equal digit *sets* —
# digits only, never the modifier marking (a cloned cell does not inherit its
# source's doubler/constant) — read digit mode through `Engine.real_digit_slots`
# (ADR-0019 dec 4/6) so the sentinel filling a singleton's second slot is never
# compared. No real `type 302` link was committed to ground-truth the wire shape;
# it is taken from the in-repo `has_live_data` reader, a one-function swap if a
# real link corrects it — the same posture 303's `corner_to_quad` records.
CLONE_TYPE = 302

# type 303 is a quadruple-clue block: `{clues: [{corner, digits}]}`. Each
# `corner` names a 2x2 block (`quadruple.corner_to_quad`); each of its
# `digits` must equal at least one of those four cells' values
# (`Engine.value_expr`, ADR-0009) — `2·d` over a doubler, combined `s_value`
# over an S-cell, the bare digit otherwise — read value mode like even/odd.
QUADRUPLE_TYPE = 303

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
