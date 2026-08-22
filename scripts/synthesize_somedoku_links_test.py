"""Guards for the synthesized somedoku corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to `line-count-distinct`
with no boxes (so a fixture can't secretly decode as plain classic sudoku
and still pass as somedoku coverage). The drift guard that the committed
file matches its synthesizer byte for byte lives in `corpus_drift_test.py`,
auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_somedoku_links as syn

from gridfind.sudokumaker import link_to_puzzle


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
