"""Tests for the accepted-link setter guide generator (ADR-0013, issue #365).

Every expectation is derived from the imported decoder constants rather than
hardcoded, so the suite tracks `sudokumaker.py` instead of drifting from it."""

from __future__ import annotations

import html
import pathlib

from gridfind import setter_guide
from gridfind.layers.regions import BOX_SHAPE
from gridfind.sudokumaker import (
    _DOUBLER_MARKER_LABELS,
    _NAMED_KILLER_CAGE_LABELS,
    _SCELL_MARKER_LABELS,
    DECODER_REGISTRY,
)

_COMMITTED_PAGE = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "accepted-link-setter-guide.html"
)

_STRUCTURAL_NAMES = {
    entry.name for entry in DECODER_REGISTRY.values() if entry.setter_doc is None
}
_SETTER_FACING_ENTRIES = [
    entry for entry in DECODER_REGISTRY.values() if entry.setter_doc is not None
]


_ALL_CAGE_NAMES = (
    _NAMED_KILLER_CAGE_LABELS | _DOUBLER_MARKER_LABELS | _SCELL_MARKER_LABELS
)


def test_every_cage_name_present_capitalized() -> None:
    # Every accepted label — canonical or synonym — appears in its capitalized
    # display form, so no recognized spelling is silently dropped from the page.
    page = setter_guide.render()
    for name in _ALL_CAGE_NAMES:
        assert name.capitalize() in page


def test_both_schroedinger_spellings_present() -> None:
    page = setter_guide.render()
    assert "schrödinger" in page.lower()
    assert "schrodinger" in page.lower()


def test_every_setter_facing_constraint_type_present() -> None:
    page = setter_guide.render()
    for entry in _SETTER_FACING_ENTRIES:
        assert entry.setter_doc is not None
        assert entry.setter_doc.display_name in page


def test_every_box_size_present() -> None:
    page = setter_guide.render()
    for size in BOX_SHAPE:
        assert str(size) in page


def test_structural_rows_omitted_from_page() -> None:
    page = setter_guide.render()
    for name in _STRUCTURAL_NAMES:
        assert name not in page


def test_per_constraint_facts_present_for_every_setter_facing_entry() -> None:
    page = setter_guide.render()
    for entry in _SETTER_FACING_ENTRIES:
        doc = entry.setter_doc
        assert doc is not None
        assert html.escape(doc.wire_block) in page
        assert html.escape(doc.decode_result) in page
        assert html.escape(doc.verdict) in page


def _assert_found_link_embedded(page: str, stem: str) -> None:
    assert stem.startswith("found-")
    url = (setter_guide._LINKS_DIR / f"{stem}.txt").read_text().strip()
    assert html.escape(url, quote=True) in page


def test_every_setter_facing_constraint_row_links_a_found_example() -> None:
    # Each supported-constraint-type row carries a working "found" corpus link.
    page = setter_guide.render()
    for entry in _SETTER_FACING_ENTRIES:
        _assert_found_link_embedded(page, setter_guide._EXAMPLE_LINK_STEMS[entry.name])


def test_every_cage_name_row_links_a_found_example() -> None:
    # Each cage-name role links its own example, so doubler and S-cell markers
    # demonstrate separately despite sharing the cosmetic-cage wire type.
    page = setter_guide.render()
    stems = {group[3] for group in setter_guide._CAGE_NAME_GROUPS}
    assert {"found-doubler-4x4", "found-scell-pin-4x4"} <= stems
    for stem in stems:
        _assert_found_link_embedded(page, stem)


def test_render_byte_equals_committed_page() -> None:
    committed = _COMMITTED_PAGE.read_text()
    assert committed == setter_guide.render()
