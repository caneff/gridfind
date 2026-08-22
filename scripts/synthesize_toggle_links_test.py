"""Guards for the synthesized global-toggle corpus.

Fast (decode only, no solve — the front-door verdict drive lives in the
on-demand `links_test` e2e suite): each link decodes to the gridfind
constraint the fixture is named for (so a `found` fixture can't secretly
drop its toggle and pass as a plain classic puzzle). The drift guard that
the committed file matches its synthesizer byte for byte lives in
`corpus_drift_test.py`, auto-discovered over every synthesizer.
"""

from __future__ import annotations

import pytest
import synthesize_toggle_links as syn

from gridfind.sudokumaker import link_to_puzzle

_EXPECTED_CONSTRAINT: dict[str, str] = {
    "found-anti-knight-4x4": "anti-knight",
    "broke-anti-knight-4x4": "anti-knight",
    "found-anti-king-6x6": "anti-king",
    "broke-anti-king-6x6": "anti-king",
    "found-x-sudoku-4x4": "negative-diagonal",
    "broke-x-sudoku-4x4": "negative-diagonal",
    "found-negative-diagonal-only-4x4": "negative-diagonal",
    "broke-negative-diagonal-only-4x4": "negative-diagonal",
    "found-positive-diagonal-only-4x4": "positive-diagonal",
    "broke-positive-diagonal-only-4x4": "positive-diagonal",
}

# The isolation fixtures each set exactly one diagonal toggle; this maps each
# to the *other* diagonal, which must be absent from the decoded constraints
# — the fact the coverage-floor x-sudoku pair can't prove, since both of its
# fixtures carry both diagonals at once.
_EXCLUDED_DIAGONAL: dict[str, str] = {
    "found-negative-diagonal-only-4x4": "positive-diagonal",
    "broke-negative-diagonal-only-4x4": "positive-diagonal",
    "found-positive-diagonal-only-4x4": "negative-diagonal",
    "broke-positive-diagonal-only-4x4": "negative-diagonal",
}


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_link_decodes_to_its_named_toggle_constraint(name: str) -> None:
    """Each fixture's link carries the toggle it is named for: decode emits the
    matching gridfind constraint. The X-sudoku fixtures carry both diagonals,
    so checking `negative-diagonal` is enough to prove the toggles decoded."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    constraint_types = {constraint.type for constraint in puzzle.constraints}
    assert _EXPECTED_CONSTRAINT[name] in constraint_types


@pytest.mark.parametrize(
    "name", sorted(_EXCLUDED_DIAGONAL), ids=sorted(_EXCLUDED_DIAGONAL)
)
def test_diagonal_only_link_excludes_the_other_diagonal(name: str) -> None:
    """Each `*-diagonal-only-*` fixture sets exactly one diagonal toggle: the
    other diagonal must not appear among the decoded constraints, proving the
    two switches are read independently rather than one standing in for
    both."""
    puzzle, _ = link_to_puzzle(syn.CORPUS[name]())
    constraint_types = {constraint.type for constraint in puzzle.constraints}
    assert _EXCLUDED_DIAGONAL[name] not in constraint_types
