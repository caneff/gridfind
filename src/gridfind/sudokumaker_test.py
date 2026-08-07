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
    Given,
    Place,
    Puzzle,
    Variant,
    WorkingState,
)
from gridfind.sudokumaker import decode_link

# The confirmed §4a classic link (issue #54). One link carries the whole
# positive corpus: given R1C6/R4C3/R7C2/R7C6, a placement at R1C1, a multi-digit
# center mark at R2C9 (`candidates 518 = 2^1+2^2+2^9`), a singleton center mark
# at R6C8 (`candidates 4 = 2^2`), and corner marks at R1C7-9 that map nowhere.
CLASSIC_LINK = (
    "https://sudokumaker.app/?puzzle="
    "N4IgZg9gTgtghgFwGoFMoGcCWEB2IBcIAjAHQCsJADCADQgAOArgF7MA2KBoOcMnhtEHEYIAFtA"
    "IgAwqMw4Aygihx6ggMYo2bdAQDaoAG5w2jfgHYAvjWBWb127ZABzTAZR58S03SMn%2BAFkc1aBw"
    "0AAV3NUw2AFk4KABrHXwADiCQ8MjouMTktOsQYKhQqAicKNj4pIJ8uzqHe0b6grU4HAATTHbEFG"
    "SyIlqG5uGh0YKXNw8vFB9jUwIyMZGmpdWV9eXhwrbO7oRegkCN51d3AmnZvwIANjXQCbPPKG8QX"
    "3nUu8%2BNr83RgF06MEcOglHA5AhkvoQAgAJ70fiURyw%2BEEIh0KAoFy4SGUGi43Fowk0ABMJL"
    "J%2BLxNCJaNJtMpFOpZLpAGYaKzWf4aJzOWQaLzeey2VzhTy%2BWLBRyRWL%2BTRrrL5WYaIrFSk"
    "aKrVXLNUrtSq1XqtXLldr1Wq-hYzRYgA"
)

# All three variants, in the order the decoder emits them.
_CLASSIC_VARIANTS = (
    Variant("rows-distinct"),
    Variant("cols-distinct"),
    Variant("regions-distinct"),
)


def test_classic_link_decodes_to_expected_puzzle_and_state() -> None:
    puzzle, state = decode_link(CLASSIC_LINK)

    assert puzzle == Puzzle(
        board=Board(size=9),
        variants=_CLASSIC_VARIANTS,
        givens=(
            Given("R1C6", 4),
            Given("R4C3", 5),
            Given("R7C2", 6),
            Given("R7C6", 8),
        ),
    )
    assert state == WorkingState(
        places=(Place("R1C1", 7),),
        candidates=(
            Candidate("R2C9", frozenset({1, 2, 9})),
            Candidate("R6C8", frozenset({2})),
        ),
    )


def test_singleton_center_mark_is_a_candidate_not_a_place() -> None:
    # `candidates 4 = 2^2` at R6C8 is a one-digit *narrowing*, not a committed
    # digit — it must never be mistaken for a placement.
    _, state = decode_link(CLASSIC_LINK)

    assert Candidate("R6C8", frozenset({2})) in state.candidates
    assert all(place.address != "R6C8" for place in state.places)


# The standard 3x3 box id per cell, derived independently of the decoder's own
# region map: region = (row // 3) * 3 + (col // 3), row-major.
_STANDARD_REGIONS = [(i // 9 // 3) * 3 + (i % 9 // 3) for i in range(81)]
_EMPTY_CELLS = [{} for _ in range(81)]
_CLASSIC_CONSTRAINTS = [{"type": 0}, {"type": 1, "regions": _STANDARD_REGIONS}]


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
    payload = _encode({"cells": cells, "constraints": _CLASSIC_CONSTRAINTS})

    _, state = decode_link(payload)

    assert state == WorkingState()


_JIGSAW_REGIONS = [8, *_STANDARD_REGIONS[1:]]  # R1C1 moved out of its box


@pytest.mark.parametrize(
    ("puzzle", "match"),
    [
        (
            {"cells": _EMPTY_CELLS, "minDigit": 0, "constraints": _CLASSIC_CONSTRAINTS},
            "minDigit",
        ),
        (
            {"cells": [{} for _ in range(80)], "constraints": _CLASSIC_CONSTRAINTS},
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
    # Each variant fails for *its own* reason, not an incidental ValueError.
    with pytest.raises(ValueError, match=match):
        decode_link(_encode(puzzle))
