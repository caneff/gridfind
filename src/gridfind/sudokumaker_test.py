"""The SudokuMaker decoder at its one seam: `decode_link(link) -> Puzzle, state`.

The positive fixture is the real classic link from decision #54 (research §4a):
givens, a placement, a multi-digit center mark `{1,2,9}`, a singleton center
mark `{2}`, and corner marks `{3}` that gridfind drops. Every rejection case is
synthesised — lz-string-compressed JSON built here — since it tests the guard,
not app fidelity.
"""

import json

import pytest
from lzstring import LZString

from gridfind.puzzle import (
    Board,
    Candidate,
    Constraint,
    Given,
    Placement,
    Puzzle,
    WorkingState,
)
from gridfind.sudokumaker import decode_link

# All three constraints, in the order the decoder emits them.
_CLASSIC_CONSTRAINTS = (
    Constraint("rows-distinct"),
    Constraint("cols-distinct"),
    Constraint("regions-distinct"),
)


def test_classic_link_decodes_to_expected_puzzle_and_state(classic_link: str) -> None:
    puzzle, state = decode_link(classic_link)

    assert puzzle == Puzzle(
        board=Board(size=9),
        constraints=_CLASSIC_CONSTRAINTS,
        givens=(
            Given("R1C6", 4),
            Given("R4C3", 5),
            Given("R7C2", 6),
            Given("R7C6", 8),
        ),
    )
    assert state == WorkingState(
        places=(Placement("R1C1", 7),),
        candidates=(
            Candidate("R2C9", frozenset({1, 2, 9})),
            Candidate("R6C8", frozenset({2})),
        ),
    )


def test_singleton_center_mark_is_a_candidate_not_a_place(classic_link: str) -> None:
    # `candidates 4 = 2^2` at R6C8 is a one-digit *narrowing*, not a committed
    # digit — it must never be mistaken for a placement.
    _, state = decode_link(classic_link)

    assert Candidate("R6C8", frozenset({2})) in state.candidates
    assert all(place.address != "R6C8" for place in state.places)


# The standard 3x3 box id per cell, derived independently of the decoder's own
# region map: region = (row // 3) * 3 + (col // 3), row-major.
_STANDARD_REGIONS = [(i // 9 // 3) * 3 + (i % 9 // 3) for i in range(81)]
_EMPTY_CELLS = [{} for _ in range(81)]
# SudokuMaker's own constraint blocks — its wire vocabulary, not gridfind's
# `Constraint`; a classic link carries the implicit type 0 and a type 1
# whose regions are the standard boxes.
_WIRE_CONSTRAINTS = [{"type": 0}, {"type": 1, "regions": _STANDARD_REGIONS}]


def _encode(puzzle: dict[str, object]) -> str:
    """A synthesised bare payload: lz-string-compressed `formatVersion 1.5.0`."""
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle}
    return LZString.compressToEncodedURIComponent(json.dumps(doc))


def test_colors_and_corner_marks_leave_the_state_empty() -> None:
    # Notations gridfind can't represent — a cell color and a corner mark — must
    # contribute nothing, so a cosmetic mark never corrupts the verdict.
    cells = [{} for _ in range(81)]
    cells[0] = {"colors": [1]}
    cells[1] = {"cornerPencilMarks": 8}
    payload = _encode({"cells": cells, "constraints": _WIRE_CONSTRAINTS})

    _, state = decode_link(payload)

    assert state == WorkingState()


_JIGSAW_REGIONS = [8, *_STANDARD_REGIONS[1:]]  # R1C1 moved out of its box


@pytest.mark.parametrize(
    ("puzzle", "match"),
    [
        (
            {"cells": _EMPTY_CELLS, "minDigit": 0, "constraints": _WIRE_CONSTRAINTS},
            "minDigit",
        ),
        (
            {"cells": [{} for _ in range(80)], "constraints": _WIRE_CONSTRAINTS},
            "81 cells",
        ),
        (
            {"cells": _EMPTY_CELLS, "constraints": [{"type": 5}]},
            "unknown constraint type",
        ),
        (
            {
                "cells": _EMPTY_CELLS,
                "constraints": [{"type": 0}, {"type": 1, "regions": _JIGSAW_REGIONS}],
            },
            "standard 3x3 partition",
        ),
    ],
    ids=["minDigit", "wrong-cell-count", "unknown-type", "jigsaw-regions"],
)
def test_non_classic_link_is_rejected(puzzle: dict[str, object], match: str) -> None:
    # Each case fails for *its own* reason, not an incidental ValueError.
    with pytest.raises(ValueError, match=match):
        decode_link(_encode(puzzle))
