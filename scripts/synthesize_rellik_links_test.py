"""Guards for the synthesized Rellik-cage corpus.

Two axes, both fast (decode only, no solve — the front-door verdict drive
lives in the on-demand `links_test` e2e suite): the committed file matches
its synthesizer byte for byte, and each link decodes to the expected
`cage` + `rellik-cage` pair over the cage's own cells and forbidden total.
"""

from __future__ import annotations

import pytest
import synthesize_rellik_links as syn

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"


@pytest.mark.parametrize(
    ("name", "cells"),
    [("found-rellik-4x4", ["R1C1", "R2C3"]), ("broke-rellik-4x4", ["R1C1", "R1C2"])],
)
def test_link_decodes_to_cage_plus_rellik_cage(name: str, cells: list[str]) -> None:
    """Each fixture's `Rellik`-named cosmetic cage decodes to a no-repeats
    `cage` plus a `rellik-cage` forbidding the labelled total 3, over the
    same cells — never a `group-sum`, which would mean the name graduated to
    an ordinary killer cage instead."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    assert Constraint("cage", params={"cells": cells}) in puzzle.constraints
    assert (
        Constraint("rellik-cage", params={"cells": cells, "sum": 3})
        in puzzle.constraints
    )
    assert all(c.type != "group-sum" for c in puzzle.constraints)
