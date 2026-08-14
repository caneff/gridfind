"""Render the accepted-link setter guide page from the decoder's own
constants (ADR-0013). `render()` is pure: it reads
`sudokumaker.DECODER_REGISTRY`, the three cage-name frozensets, and
`BOX_SHAPE`, fills them into `setter_guide_template.html`'s `$slot`
placeholders, and returns the full page HTML. The committed copy at
`docs/accepted-link-setter-guide.html` is a build product of this function —
`setter_guide_test.py`'s freshness test fails the moment the two diverge."""

from __future__ import annotations

import html
import pathlib
import string

from gridfind.layers.regions import BOX_SHAPE
from gridfind.sudokumaker import (
    _DOUBLER_MARKER_LABELS,
    _NAMED_KILLER_CAGE_LABELS,
    _SCELL_MARKER_LABELS,
    DECODER_REGISTRY,
)

_TEMPLATE_PATH = pathlib.Path(__file__).with_name("setter_guide_template.html")
_LINKS_DIR = pathlib.Path(__file__).with_name("links")

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
}

# One canonical display label per cage-name role, paired with the frozenset the
# decoder actually matches against, the role blurb, and a "found" corpus example.
# "Canonical" is a presentation choice — the decoder treats every label in a set
# identically (ADR-0013) — so it lives here, not in sudokumaker. The remaining
# labels render as the row's comma-separated "other accepted names". Each role
# links a distinct example, so the doubler and S-cell markers demonstrate
# separately even though they share the one cosmetic-cage wire type.
_CAGE_NAME_GROUPS: tuple[tuple[str, frozenset[str], str, str], ...] = (
    (
        "sum",
        _NAMED_KILLER_CAGE_LABELS,
        "Decorative label on a genuine killer cage",
        "found-cage-4x4",
    ),
    ("doubler", _DOUBLER_MARKER_LABELS, "Doubler position marker", "found-doubler-4x4"),
    (
        "s-cell",
        _SCELL_MARKER_LABELS,
        (
            "S-cell / Schrödinger position marker; the cage's numeric label supplies "
            "each marked cell's directive — a pin (two digits), a half-pin (one "
            "digit), or bare (no label)"
        ),
        "found-scell-pin-4x4",
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
    for entry in DECODER_REGISTRY.values():
        if entry.setter_doc is None:
            continue
        link = _example_link_cell(_EXAMPLE_LINK_STEMS[entry.name])
        rows.append(
            f"<tr><td>{html.escape(entry.setter_doc.display_name)}</td>"
            f"<td>{link}</td></tr>"
        )
    return "\n".join(rows)


def _box_size_rows() -> str:
    rows = []
    for size in sorted(BOX_SHAPE):
        rows_count, cols_count = BOX_SHAPE[size]
        rows.append(f"<tr><td>{size}</td><td>{rows_count} x {cols_count}</td></tr>")
    return "\n".join(rows)


def _constraint_sections() -> str:
    sections: list[str] = []
    for entry in DECODER_REGISTRY.values():
        doc = entry.setter_doc
        if doc is None:
            continue
        sections.append(
            f'<section class="constraint">\n'
            f"<h3>{html.escape(doc.display_name)}</h3>\n"
            f"<dl>\n"
            f"<dt>Wire block</dt><dd>{html.escape(doc.wire_block)}</dd>\n"
            f"<dt>Decodes to</dt><dd>{html.escape(doc.decode_result)}</dd>\n"
            f"<dt>Verdict</dt><dd>{html.escape(doc.verdict)}</dd>\n"
            f"</dl>\n"
            f"</section>"
        )
    return "\n".join(sections)


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
