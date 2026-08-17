"""Tests for the accepted-link setter guide generator (ADR-0013).

Every expectation is derived from the imported decoder constants rather than
hardcoded, so the suite tracks the `sudokumaker` decoder constants instead of
drifting from them."""

from __future__ import annotations

import html
import pathlib
import re

import pytest

from gridfind import setter_guide
from gridfind.layers.regions import BOX_SHAPE
from gridfind.sudokumaker.markers import MARKER_LABELS
from gridfind.sudokumaker.registry import DECODER_REGISTRY

_COMMITTED_PAGE = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "accepted-link-setter-guide.html"
)

_STRUCTURAL_NAMES = {
    entry.name
    for wire_type, entry in DECODER_REGISTRY.items()
    if wire_type not in setter_guide.SETTER_DOCS
}
# Each setter-facing entry paired with its `SetterDoc` — the two tables are
# keyed by the same wire type, so every row here has both halves.
_SETTER_FACING_ENTRIES = [
    (entry, setter_guide.SETTER_DOCS[wire_type])
    for wire_type, entry in DECODER_REGISTRY.items()
    if wire_type in setter_guide.SETTER_DOCS
]


_ALL_CAGE_NAMES: frozenset[str] = frozenset().union(*MARKER_LABELS.values())


@pytest.mark.parametrize(
    "wire_type",
    [t for t in DECODER_REGISTRY if t not in (0, 1)],
)
def test_non_structural_wire_types_carry_a_populated_setter_doc(wire_type: int) -> None:
    # Every setter-facing constraint owes the accepted-link setter guide its
    # display name, wire block, decode result, and verdict (map #335, #336).
    doc = setter_guide.SETTER_DOCS[wire_type]
    assert doc.display_name
    assert doc.wire_block
    assert doc.decode_result
    assert doc.verdict


@pytest.mark.parametrize("wire_type", [0, 1])
def test_structural_wire_types_carry_no_setter_doc(wire_type: int) -> None:
    # `type 0` (givens) and `type 1` (regions) aren't setter-drawn constraints,
    # so their absence from `SETTER_DOCS` marks them as not setter-facing
    # without a separate skip-list.
    assert wire_type not in setter_guide.SETTER_DOCS


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
    for _entry, doc in _SETTER_FACING_ENTRIES:
        assert doc.display_name in page


def test_every_box_size_present() -> None:
    page = setter_guide.render()
    for size in BOX_SHAPE:
        assert str(size) in page


def _section(page: str, section_id: str) -> str:
    """The inner HTML of the flat (non-nested) `<section id="...">` block."""
    match = re.search(
        rf'<section id="{re.escape(section_id)}">(.*?)</section>', page, re.DOTALL
    )
    assert match is not None, f"no section {section_id!r}"
    return match.group(1)


def test_structural_rows_omitted_from_setter_facing_sections() -> None:
    # The structural registry rows (givens, regions) must not appear in the
    # code-generated setter-facing table or per-constraint cards. Prose elsewhere
    # may use the ordinary word "regions" (drawing them for a non-box size), so
    # the check is scoped to the generated sections, not the whole page.
    page = setter_guide.render()
    generated = _section(page, "constraint-types") + _section(page, "per-constraint")
    for name in _STRUCTURAL_NAMES:
        assert name not in generated


def test_per_constraint_facts_present_for_every_setter_facing_entry() -> None:
    page = setter_guide.render()
    for _entry, doc in _SETTER_FACING_ENTRIES:
        assert html.escape(doc.wire_block) in page
        assert html.escape(doc.decode_result) in page
        assert html.escape(doc.verdict) in page


def _assert_found_link_embedded(page: str, stem: str) -> None:
    assert stem.startswith("found-")
    url = (setter_guide._LINKS_DIR / f"{stem}.txt").read_text().strip()
    assert html.escape(url, quote=True) in page


def test_every_setter_facing_constraint_row_links_a_found_example() -> None:
    page = setter_guide.render()
    for entry, _doc in _SETTER_FACING_ENTRIES:
        _assert_found_link_embedded(page, setter_guide._EXAMPLE_LINK_STEMS[entry.name])


def test_every_cage_name_row_links_a_found_example() -> None:
    # Each cage-name role links its own example, so doubler and S-cell markers
    # demonstrate separately despite sharing the cosmetic-cage wire type.
    page = setter_guide.render()
    stems = {group[3] for group in setter_guide._CAGE_NAME_GROUPS}
    assert {"found-doubler-4x4", "found-scell-pin-4x4"} <= stems
    for stem in stems:
        _assert_found_link_embedded(page, stem)


def _draw_action_text(page: str, name: str) -> str | None:
    """The visible text of the `data-constraint="{name}"` draw-action element,
    tags stripped, or `None` if no such element is rendered. `None` and `""`
    are kept distinct so a missing draw-action and an empty one fail with
    different reasons."""
    match = re.search(
        rf'<p class="draw-action" data-constraint="{re.escape(name)}">(.*?)</p>',
        page,
        re.DOTALL,
    )
    if match is None:
        return None
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def test_every_non_structural_constraint_has_a_draw_action() -> None:
    # Every setter-facing constraint carries a non-empty SudokuMaker draw-action
    # keyed by its registry name, so adding a constraint and forgetting its
    # how-to-draw fails here.
    page = setter_guide.render()
    for entry, _doc in _SETTER_FACING_ENTRIES:
        text = _draw_action_text(page, entry.name)
        assert text is not None, f"no draw-action for {entry.name}"
        assert text, f"empty draw-action for {entry.name}"


def test_underivable_draw_actions_marked_provisional() -> None:
    # The two UI gestures the constraint map could not derive from repo sources —
    # drawing a jigsaw region and naming a cosmetic cage — are flagged, never
    # invented.
    page = setter_guide.render()
    for gesture in ("jigsaw-region", "cosmetic-cage-naming"):
        assert f'class="provisional" data-provisional="{gesture}"' in page


def test_required_narrative_sections_present() -> None:
    page = setter_guide.render()
    for section_id in ("intro", "state-under-test", "other-sizes", "troubleshooting"):
        assert f'id="{section_id}"' in page


def test_links_the_link_formats_research_doc() -> None:
    page = setter_guide.render()
    assert "research/sudoku-link-formats.md" in page


def test_never_mentions_the_color_or_flag_channel() -> None:
    # The page declares doublers and S-cells only through named cosmetic cages,
    # and never names a color-bit or CLI-flag channel.
    page = setter_guide.render().lower()
    for phrase in ("red bit", "red-bit", "color bit", "color-marked", "colour"):
        assert phrase not in page, f"page mentions retired channel: {phrase!r}"
    for flag in ("--schrodinger", "--doubler"):
        assert flag not in page, f"page mentions retired flag: {flag!r}"


def test_render_byte_equals_committed_page() -> None:
    committed = _COMMITTED_PAGE.read_text()
    assert committed == setter_guide.render()
