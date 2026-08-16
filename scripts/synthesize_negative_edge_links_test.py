"""Guards for the synthesized negative-edge-clue corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive
lives in the on-demand `links_test` e2e suite): the committed file matches
its synthesizer byte for byte, and each link decodes to the `pair-difference`
constraint its clue names, with the `negative` list still present on the raw
wire block — proof the fixture actually exercises the warn-and-drop path
rather than accidentally shipping an empty list.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
import synthesize_negative_edge_links as syn

from gridfind.sudokumaker import decode_document, decode_link


def _wire_negative(link: str) -> list[object]:
    puzzle = cast("dict[str, Any]", decode_document(link)["puzzle"])
    constraints = cast("list[dict[str, Any]]", puzzle["constraints"])
    block = next(c for c in constraints if c.get("type") == 200)
    return cast("list[object]", block["negative"])


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_carries_a_non_empty_negative_list(name: str) -> None:
    """Each fixture's wire block actually carries the non-empty `negative`
    list the corpus is meant to cover — the gap issue #487 closes."""
    assert _wire_negative(syn.CORPUS[name]()) == [2]


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_its_kropki_constraint(name: str) -> None:
    """Each fixture's link still decodes its positive clue to a
    `pair-difference` constraint despite the non-empty `negative` list —
    proof the drop only warns, it never swallows the positive clue."""
    puzzle, _ = decode_link(syn.CORPUS[name]())
    constraint_types = {constraint.type for constraint in puzzle.constraints}
    assert "pair-difference" in constraint_types
