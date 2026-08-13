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

_CAGE_NAME_ROLES: dict[str, str] = {
    **dict.fromkeys(
        _NAMED_KILLER_CAGE_LABELS, "Decorative label on a genuine killer cage"
    ),
    **dict.fromkeys(_DOUBLER_MARKER_LABELS, "Doubler position marker"),
    **dict.fromkeys(_SCELL_MARKER_LABELS, "S-cell / Schrödinger position marker"),
}


def _cage_name_rows() -> str:
    rows = []
    for name in sorted(_CAGE_NAME_ROLES):
        role = _CAGE_NAME_ROLES[name]
        rows.append(
            f"<tr><td>{html.escape(name)}</td><td>{html.escape(role)}</td></tr>"
        )
    return "\n".join(rows)


def _constraint_type_rows() -> str:
    rows = []
    for entry in DECODER_REGISTRY.values():
        if entry.setter_doc is None:
            continue
        rows.append(f"<tr><td>{html.escape(entry.setter_doc.display_name)}</td></tr>")
    return "\n".join(rows)


def _box_size_rows() -> str:
    rows = []
    for size in sorted(BOX_SHAPE):
        rows_count, cols_count = BOX_SHAPE[size]
        rows.append(f"<tr><td>{size}</td><td>{rows_count} x {cols_count}</td></tr>")
    return "\n".join(rows)


def _constraint_sections() -> str:
    sections = []
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
        INTRO="",
        CAGE_NAME_ROWS=_cage_name_rows(),
        CONSTRAINT_TYPE_ROWS=_constraint_type_rows(),
        BOX_SIZE_ROWS=_box_size_rows(),
        CONSTRAINT_SECTIONS=_constraint_sections(),
        TROUBLESHOOTING="",
    )
