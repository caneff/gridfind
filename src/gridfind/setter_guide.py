"""Render the accepted-link setter guide page from the decoder's own
constants (ADR-0013). `render()` is pure: it reads
`sudokumaker.registry.DECODER_REGISTRY`, this module's own `SETTER_DOCS`
table, `sudokumaker.markers.MARKER_LABELS`, and `BOX_SHAPE`, fills them into
`setter_guide_template.html`'s `$slot` placeholders, and returns the full page
HTML. The committed copy at `docs/accepted-link-setter-guide.html` is a build
product of this function — `setter_guide_test.py`'s freshness test fails the
moment the two diverge."""

from __future__ import annotations

import html
import pathlib
import string
from dataclasses import dataclass

from gridfind.cell_geometry import BOX_SHAPE
from gridfind.sudokumaker.markers import MARKER_LABELS
from gridfind.sudokumaker.registry import DECODER_REGISTRY
from gridfind.sudokumaker.wire_types import (
    ANTI_KING_TYPE,
    ANTI_KNIGHT_TYPE,
    CAGE_TYPE,
    COSMETIC_CAGE_TYPE,
    KROPKI_BLACK_TYPE,
    KROPKI_WHITE_TYPE,
    NEGATIVE_DIAGONAL_TYPE,
    POSITIVE_DIAGONAL_TYPE,
    THERMO_TYPE,
    XV_TYPE,
)

_TEMPLATE_PATH = pathlib.Path(__file__).with_name("setter_guide_template.html")
_LINKS_DIR = pathlib.Path(__file__).with_name("links")


@dataclass(frozen=True)
class SetterDoc:
    """The setter-facing facts a `DECODER_REGISTRY` wire type owes the
    accepted-link setter guide (ADR-0013): the display name a setter
    recognizes, the wire block gridfind reads, what it decodes to, and its
    accept/ignore/reject verdict. Sourced from
    `docs/research/accepted-link-constraint-map.md` §3 — the SudokuMaker
    draw-action itself is deliberately absent; ADR-0013 keeps it in the page
    template instead."""

    display_name: str
    wire_block: str
    decode_result: str
    verdict: str


# The setter-facing reference facts for every `DECODER_REGISTRY` wire type a
# setter draws directly, keyed by wire type. The two structural rows (`0`
# givens, `1` regions) carry no entry — they aren't constraints a setter
# draws — so `_setter_doc_rows`/`_constraint_sections` skip any wire type
# missing from this table rather than relying on a separate skip-list.
SETTER_DOCS: dict[int, SetterDoc] = {
    KROPKI_WHITE_TYPE: SetterDoc(
        display_name="White Kropki (Difference Dot)",
        wire_block="type 200 {clues:[{value, edge}], negative:[…]}",
        decode_result="One pair-difference Constraint per clue; value maps"
        " verbatim to diff. A non-empty negative list adds one negated"
        " pair-difference per listed value, over every"
        " orthogonally-adjacent pair not already carrying a dot.",
        verdict="Accept the positive clues and enforce a non-empty"
        " negative list. An edge naming no in-bounds pair raises"
        " ValueError. disabled blocks are skipped.",
    ),
    KROPKI_BLACK_TYPE: SetterDoc(
        display_name="Black Kropki (Ratio Dot)",
        wire_block="type 201 {clues:[{value, edge}], negative:[…]} —"
        " same shape as white kropki.",
        decode_result="One pair-ratio Constraint per clue; value maps verbatim to k.",
        verdict="Accept the positive clues; negative is warn-and-dropped."
        " A non-integer value raises ValueError, as does an out-of-range"
        " edge. disabled blocks are skipped.",
    ),
    XV_TYPE: SetterDoc(
        display_name="XV",
        wire_block="type 202 {clues:[{value, edge}], negative:[…]} —"
        " value is 10 (X) or 5 (V).",
        decode_result="One aliased group-sum Constraint per clue: 10"
        " selects the X alias, 5 the V alias.",
        verdict="Accept clues whose value is 10 or 5; any other value"
        " raises ValueError. negative is warn-and-dropped; disabled"
        " blocks are skipped.",
    ),
    CAGE_TYPE: SetterDoc(
        display_name="Killer Cage",
        wire_block="type 301 {cages:[{cells, value}]}.",
        decode_result="Each cage becomes a no-repeats cage Constraint;"
        " a positive value additionally emits a group-sum over the same"
        " cells.",
        verdict="Accept. value 0 or absent is SudokuMaker's own no-sum"
        " cage — cage alone, no group-sum. disabled blocks are skipped;"
        " an empty cages list adds nothing.",
    ),
    COSMETIC_CAGE_TYPE: SetterDoc(
        display_name="Cosmetic Cage",
        wire_block="type 2001 {cages:[{value:str, cells}], name?,"
        " style?} — value is a string; a top-level name may mark the"
        " block as a variant declaration.",
        decode_result="name classifies the block: Sum/Killer decodes as a"
        " killer cage (a numeric non-zero string value graduates to a"
        " group-sum); Doubler emits per-cell modifier directives;"
        " S-cell/Schrödinger/Schrodinger infers Schrödinger-ness and"
        " routes its cells through the per-cell S-cell branch; absent or"
        " unrecognized carries no rule.",
        verdict="Accept a recognized name. An unnamed or unrecognized"
        " name is warn-and-dropped to stderr, naming the block."
        " disabled blocks are skipped.",
    ),
    THERMO_TYPE: SetterDoc(
        display_name="Thermometer",
        wire_block="type 300 {slow:bool, thermometers:[[cell indices,"
        " bulb first], …]}.",
        decode_result="One thermo Constraint per path, order preserved"
        " (bulb first); slow rides onto every path in the block.",
        verdict="Accept. disabled blocks are skipped; an empty"
        " thermometers list adds nothing.",
    ),
    NEGATIVE_DIAGONAL_TYPE: SetterDoc(
        display_name="Negative Diagonal (\\)",
        wire_block="type 10 {style?} — a bare toggle; style is cosmetic.",
        decode_result="One negative-diagonal Constraint: the `\\` diagonal"
        " holds all-different digits. Independent of the positive diagonal.",
        verdict="Accept an enabled block. A disabled block is skipped; the"
        " cosmetic style is ignored.",
    ),
    POSITIVE_DIAGONAL_TYPE: SetterDoc(
        display_name="Positive Diagonal (/)",
        wire_block="type 11 {style?} — a bare toggle; style is cosmetic.",
        decode_result="One positive-diagonal Constraint: the `/` diagonal"
        " holds all-different digits. Both toggles together are X-sudoku.",
        verdict="Accept an enabled block. A disabled block is skipped; the"
        " cosmetic style is ignored.",
    ),
    ANTI_KING_TYPE: SetterDoc(
        display_name="Anti-King",
        wire_block="type 12 — a bare toggle, no payload.",
        decode_result="One anti-king Constraint: no two cells a king's step"
        " apart share a digit.",
        verdict="Accept an enabled block. A disabled block is skipped.",
    ),
    ANTI_KNIGHT_TYPE: SetterDoc(
        display_name="Anti-Knight",
        wire_block="type 13 — a bare toggle, no payload.",
        decode_result="One anti-knight Constraint: no two cells a knight's"
        " hop apart share a digit.",
        verdict="Accept an enabled block. A disabled block is skipped.",
    ),
}

# One representative "found" corpus link per setter-facing constraint, keyed by
# its DECODER_REGISTRY entry name. Each row of the supported-constraint-types
# table links its example; a KeyError here (a setter-facing entry with no
# example) or a missing file fails generation loudly rather than shipping a guide
# with a hole.
_EXAMPLE_LINK_STEMS: dict[str, str] = {
    "white-kropki": "found-kropki-4x4",
    "black-kropki": "found-black-kropki-4x4",
    "XV": "found-xv-9x9",
    "killer-cage": "found-cage-4x4",
    "cosmetic-cage": "found-doubler-4x4",
    "thermo": "found-thermo-4x4",
    "anti-knight": "found-anti-knight-4x4",
    "anti-king": "found-anti-king-6x6",
    "negative-diagonal": "found-x-sudoku-4x4",
    "positive-diagonal": "found-x-sudoku-4x4",
}

# One canonical display label per cage-name role, paired with `MARKER_LABELS`'s
# alias set for that role, the role blurb, and a "found" corpus example.
# "Canonical" is a presentation choice — the decoder treats every alias in a
# role identically (ADR-0013) — so it lives here, not in sudokumaker. The
# remaining aliases render as the row's comma-separated "other accepted
# names". Each role links a distinct example, so the doubler and S-cell
# markers demonstrate separately even though they share the one cosmetic-cage
# wire type.
_CAGE_NAME_GROUPS: tuple[tuple[str, frozenset[str], str, str], ...] = (
    (
        "sum",
        MARKER_LABELS["killer"],
        "Decorative label on a genuine killer cage",
        "found-cage-4x4",
    ),
    (
        "equality",
        MARKER_LABELS["equality"],
        (
            "Equality cage — all digits distinct, with equal counts of "
            "even/odd and low/high digits; an odd cell count is refused as "
            "malformed"
        ),
        "found-equality-9x9",
    ),
    (
        "rellik",
        MARKER_LABELS["rellik"],
        ("Anti-cage: no group of the cage's cells may sum to its labelled total"),
        "found-rellik-4x4",
    ),
    (
        "doubler",
        MARKER_LABELS["doubler"],
        "Doubler position marker",
        "found-doubler-4x4",
    ),
    (
        "constant",
        MARKER_LABELS["constant"],
        (
            "Constant modifier position marker; k is read from the cage name "
            "itself (Constant 5, Constant -3, …) rather than a per-cage value — "
            "Nullifier is the k = 0 spelling"
        ),
        "found-constant-4x4",
    ),
    (
        "s-cell",
        MARKER_LABELS["s-cell"],
        (
            "S-cell / Schrödinger position marker; the cage's numeric label supplies "
            "each marked cell's directive — a pin (two digits), a half-pin (one "
            "digit), or bare (no label)"
        ),
        "found-scell-pin-4x4",
    ),
    (
        "somedoku",
        MARKER_LABELS["somedoku"],
        (
            "Global flag turning on the row-n/column-n distinct-count rule in "
            "place of classic uniqueness; the cage's cells and value are "
            "ignored, and the same name is also accepted on a type 1000 "
            "custom constraint"
        ),
        "found-somedoku-4x4",
    ),
)


def _example_link_cell(stem: str) -> str:
    """An `<a>` to the corpus link `stem` (its filename as the visible text, its
    SudokuMaker URL as the href), read live from `links/` so it can never go
    stale against the corpus."""
    url = (_LINKS_DIR / f"{stem}.txt").read_text().strip()
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(stem)}</a>'


def _cage_name_rows() -> str:
    rows: list[str] = []
    for canonical, labels, role, stem in _CAGE_NAME_GROUPS:
        others = ", ".join(name.capitalize() for name in sorted(labels - {canonical}))
        rows.append(
            f"<tr><td>{html.escape(canonical.capitalize())}</td>"
            f"<td>{html.escape(role)}</td>"
            f"<td>{html.escape(others)}</td>"
            f"<td>{_example_link_cell(stem)}</td></tr>"
        )
    return "\n".join(rows)


def _constraint_type_rows() -> str:
    rows: list[str] = []
    for wire_type, entry in DECODER_REGISTRY.items():
        doc = SETTER_DOCS.get(wire_type)
        if doc is None:
            continue
        link = _example_link_cell(_EXAMPLE_LINK_STEMS[entry.name])
        rows.append(f"<tr><td>{html.escape(doc.display_name)}</td><td>{link}</td></tr>")
    return "\n".join(rows)


def _box_size_rows() -> str:
    rows = []
    for size in sorted(BOX_SHAPE):
        rows_count, cols_count = BOX_SHAPE[size]
        rows.append(f"<tr><td>{size}</td><td>{rows_count} x {cols_count}</td></tr>")
    return "\n".join(rows)


def _constraint_section(doc: SetterDoc) -> str:
    return (
        f'<section class="constraint">\n'
        f"<h3>{html.escape(doc.display_name)}</h3>\n"
        f"<dl>\n"
        f"<dt>Wire block</dt><dd>{html.escape(doc.wire_block)}</dd>\n"
        f"<dt>Decodes to</dt><dd>{html.escape(doc.decode_result)}</dd>\n"
        f"<dt>Verdict</dt><dd>{html.escape(doc.verdict)}</dd>\n"
        f"</dl>\n"
        f"</section>"
    )


def _constraint_sections() -> str:
    return "\n".join(_constraint_section(doc) for doc in SETTER_DOCS.values())


def render() -> str:
    """The full setter-guide page as static HTML. Pure: no file writes, no
    network — a caller (the `just` target's writer script, or a test
    comparing against the committed copy) decides what to do with the
    string."""
    template = string.Template(_TEMPLATE_PATH.read_text())
    return template.substitute(
        CAGE_NAME_ROWS=_cage_name_rows(),
        CONSTRAINT_TYPE_ROWS=_constraint_type_rows(),
        BOX_SIZE_ROWS=_box_size_rows(),
        CONSTRAINT_SECTIONS=_constraint_sections(),
    )
