"""Guards for the synthesized somedoku corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive
lives in the on-demand `links_test` e2e suite): the committed file matches
its synthesizer byte for byte, and each link decodes to `line-count-distinct`
with no boxes (so a fixture can't secretly decode as plain classic sudoku
and still pass as somedoku coverage).
"""

from __future__ import annotations

import pytest
import synthesize_somedoku_links as syn

from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_line_count_distinct_alone(name: str) -> None:
    """Each fixture's link carries the somedoku flag: decode emits
    `line-count-distinct` in place of the classic
    `rows-distinct`/`cols-distinct`/`regions-distinct` triplet."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    constraint_types = {constraint.type for constraint in puzzle.constraints}
    assert "line-count-distinct" in constraint_types
    assert "rows-distinct" not in constraint_types
    assert "cols-distinct" not in constraint_types
    assert "regions-distinct" not in constraint_types
