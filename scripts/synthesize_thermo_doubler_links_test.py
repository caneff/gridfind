"""Guards for the synthesized thermo-over-a-doubler-board corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive
lives in the on-demand `links_test` e2e suite): the committed file matches
its synthesizer byte for byte, and each link decodes the length-2 thermo
path and the `doubler` constraint the verdict turns on.
"""

from __future__ import annotations

import pytest
import synthesize_thermo_doubler_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_the_thermo_path_and_the_doubler(name: str) -> None:
    """Both fixtures carry the same length-2 thermo path and a `doubler`
    constraint — only the two links' givens differ, not their decoded
    ruleset."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2"], "slow": False})
        in puzzle.constraints
    )
    assert Constraint("doubler", params={}) in puzzle.constraints
