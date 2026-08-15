"""Guards for the synthesized global-toggle corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive lives
in the on-demand `links_test` e2e suite): the committed file matches its
synthesizer byte for byte, and each link decodes to the gridfind constraint the
fixture is named for (so a `found` fixture can't secretly drop its toggle and
pass as a plain classic puzzle).
"""

from __future__ import annotations

import pytest
import synthesize_toggle_links as syn

from gridfind.sudokumaker import decode_link

_EXPECTED_CONSTRAINT: dict[str, str] = {
    "found-anti-knight-4x4": "anti-knight",
    "broke-anti-knight-4x4": "anti-knight",
    "found-anti-king-6x6": "anti-king",
    "broke-anti-king-6x6": "anti-king",
    "found-x-sudoku-4x4": "negative-diagonal",
    "broke-x-sudoku-4x4": "negative-diagonal",
}


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_its_named_toggle_constraint(name: str) -> None:
    """Each fixture's link carries the toggle it is named for: decode emits the
    matching gridfind constraint. The X-sudoku fixtures carry both diagonals,
    so checking `negative-diagonal` is enough to prove the toggles decoded."""
    puzzle, _ = decode_link(syn.CORPUS[name]())
    constraint_types = {constraint.type for constraint in puzzle.constraints}
    assert _EXPECTED_CONSTRAINT[name] in constraint_types
