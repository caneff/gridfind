"""The SudokuMaker decoder at its one seam: `decode_link(link) -> Puzzle, state`.

The positive fixture is the real classic link from decision #54 (research §4a):
givens, a placement, a multi-digit center mark `{1,2,9}`, a singleton center
mark `{2}`, and corner marks `{3}` that gridfind drops. Every rejection case is
synthesised — lz-string-compressed JSON built here — since it tests the guard,
not app fidelity.
"""

import json
from typing import Any

import pytest
from lzstring import LZString

from gridfind.puzzle import (
    BareSCell,
    Board,
    Candidate,
    Constraint,
    Given,
    HalfSCell,
    Placement,
    Puzzle,
    SCellPin,
    SingletonPin,
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
    ],
    ids=["minDigit", "wrong-cell-count", "unknown-type"],
)
def test_non_classic_link_is_rejected(puzzle: dict[str, object], match: str) -> None:
    # Each case fails for *its own* reason, not an incidental ValueError.
    with pytest.raises(ValueError, match=match):
        decode_link(_encode(puzzle))


def test_jigsaw_regions_decode_into_constraint_params() -> None:
    # A type 1 link whose regions differ from the standard 3x3 partition is no
    # longer refused (issue #125): it decodes with the setter's own matrix
    # carried on the regions-distinct constraint's params.
    payload = _encode(
        {
            "cells": _EMPTY_CELLS,
            "constraints": [{"type": 0}, {"type": 1, "regions": _JIGSAW_REGIONS}],
        }
    )

    puzzle, _ = decode_link(payload)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint.params == {"regions": _JIGSAW_REGIONS}


# --- --schrodinger ingest (issue #143) ---------------------------------

# A schrodinger link's own cosmetic vocabulary: unknown types the decoder
# must ignore (not reject) under --schrodinger, plus a disabled duplicate of
# the classic type-1 regions matrix, which must lose to the enabled one.
_SCHRODINGER_WIRE_CONSTRAINTS = [
    {"type": 0},
    {"type": 1, "regions": _STANDARD_REGIONS},
    {"type": 1, "regions": _JIGSAW_REGIONS, "disabled": True},
    {"type": 2003},
    {"type": 303, "disabled": True},
]


def _schrodinger_link(cells: list[dict[str, object]], *, min_digit: int = 0) -> str:
    """A synthesised Schrödinger-flavored link: `minDigit`, the cosmetic
    constraint mix a real link carries, and a caller-supplied `cells` array."""
    return _encode(
        {
            "cells": cells,
            "minDigit": min_digit,
            "constraints": _SCHRODINGER_WIRE_CONSTRAINTS,
        }
    )


def test_schrodinger_link_reads_domain_and_synthesizes_constraint() -> None:
    payload = _schrodinger_link(_EMPTY_CELLS, min_digit=0)

    puzzle, _ = decode_link(payload, schrodinger=True, reading="classic")

    assert puzzle.board == Board(size=9, values=range(10))
    assert Constraint("schrodinger") in puzzle.constraints


def test_schrodinger_link_ignores_cosmetic_and_disabled_constraints() -> None:
    # The real link's 13 constraints include cosmetic types the classic-only
    # guard would otherwise reject outright, plus a disabled duplicate of the
    # regions matrix — both ignored under --schrodinger.
    payload = _schrodinger_link(_EMPTY_CELLS)

    puzzle, _ = decode_link(payload, schrodinger=True)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint == Constraint("regions-distinct")


def test_schrodinger_min_digit_defaults_to_one_when_absent() -> None:
    payload = _encode(
        {"cells": _EMPTY_CELLS, "constraints": _SCHRODINGER_WIRE_CONSTRAINTS}
    )

    puzzle, _ = decode_link(payload, schrodinger=True)

    assert puzzle.board.values == range(1, 11)


def test_unsupported_reading_is_refused() -> None:
    payload = _schrodinger_link(_EMPTY_CELLS)

    with pytest.raises(ValueError, match="reading"):
        decode_link(payload, schrodinger=True, reading="sum-valued")


def _mask(digits: set[int]) -> int:
    total = 0
    for d in digits:
        total |= 1 << d
    return total


@pytest.mark.parametrize(
    ("cell", "expected_s_directive", "expected_candidate"),
    [
        ({"given": True, "value": 4}, None, None),
        ({"value": 3}, SingletonPin("R1C1", 3), None),
        (
            {"colors": 50, "candidates": _mask({2, 7})},  # red plus decoration
            SCellPin("R1C1", frozenset({2, 7})),
            None,
        ),
        (
            {"colors": 2, "candidates": _mask({4})},
            HalfSCell("R1C1", 4),
            None,
        ),
        ({"colors": 2}, BareSCell("R1C1"), None),
        (
            {"colors": 2, "candidates": _mask({1, 2, 3})},
            BareSCell("R1C1"),
            Candidate("R1C1", frozenset({1, 2, 3})),
        ),
    ],
    ids=[
        "given",
        "singleton-pin",
        "s-cell-pin",
        "half-s-cell",
        "bare-s-cell",
        "bare-s-cell-marks",
    ],
)
def test_schrodinger_cell_encoding_table(
    cell: dict[str, Any],
    expected_s_directive: object,
    expected_candidate: Candidate | None,
) -> None:
    cells = list(_EMPTY_CELLS)
    cells[0] = cell
    payload = _schrodinger_link(cells)

    puzzle, state = decode_link(payload, schrodinger=True)

    if cell.get("given"):
        assert Given("R1C1", cell["value"]) in puzzle.givens
    if expected_s_directive is not None:
        assert expected_s_directive in state.s_directives
    else:
        assert all(d.address != "R1C1" for d in state.s_directives)
    if expected_candidate is not None:
        assert expected_candidate in state.candidates
    else:
        assert all(c.address != "R1C1" for c in state.candidates)


def test_red_cell_with_a_value_is_rejected() -> None:
    cells = list(_EMPTY_CELLS)
    cells[0] = {"colors": 2, "value": 9}
    payload = _schrodinger_link(cells)

    with pytest.raises(ValueError, match="R1C1"):
        decode_link(payload, schrodinger=True)
