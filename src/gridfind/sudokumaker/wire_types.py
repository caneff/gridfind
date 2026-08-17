"""The SudokuMaker wire-`type` integer vocabulary: one constant per type
`decode_link` recognizes, the shared home every per-type decoder and
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
