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
from hypothesis import given as hyp_given
from hypothesis import strategies as st
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
            {"cells": [{} for _ in range(80)], "constraints": _WIRE_CONSTRAINTS},
            "do not match size",
        ),
        (
            {"cells": _EMPTY_CELLS, "constraints": [{"type": 5}]},
            "unknown constraint type",
        ),
        # A non-square shape: width 6 over 54 cells derives 9 rows (§4b's 6x9).
        (
            {
                "cells": [{} for _ in range(54)],
                "width": 6,
                "constraints": [{"type": 0}],
            },
            "not a square grid",
        ),
        # A declared size that the cell count contradicts.
        (
            {"cells": _EMPTY_CELLS, "size": 6, "constraints": [{"type": 0}]},
            "do not match size",
        ),
        # A domain that doesn't span the board: 0..5 is six digits for a 9x9.
        (
            {
                "cells": _EMPTY_CELLS,
                "minDigit": 0,
                "maxDigit": 5,
                "constraints": _WIRE_CONSTRAINTS,
            },
            "is not 9 digits",
        ),
    ],
    ids=[
        "wrong-cell-count",
        "unknown-type",
        "non-square",
        "size-mismatch",
        "bad-domain-span",
    ],
)
def test_non_classic_link_is_rejected(puzzle: dict[str, object], match: str) -> None:
    # Each case fails for *its own* reason, not an incidental ValueError.
    with pytest.raises(ValueError, match=match):
        decode_link(_encode(puzzle))


def test_link_without_type_one_is_a_latin_square() -> None:
    # No `type 1` regions block means the setter asked for no regions — rows and
    # columns distinct only. gridfind must not invent boxes (the box tiling is
    # supplied only when the link carries the box matrix). A real boxed
    # SudokuMaker puzzle always ships its boxes as an explicit `type 1`.
    payload = _encode({"cells": _EMPTY_CELLS, "constraints": [{"type": 0}]})

    puzzle, _ = decode_link(payload)

    assert Constraint("regions-distinct") not in puzzle.constraints
    assert all(c.type != "regions-distinct" for c in puzzle.constraints)
    assert puzzle.constraints == (
        Constraint("rows-distinct"),
        Constraint("cols-distinct"),
    )


def test_untileable_latin_square_decodes() -> None:
    # A 5x5 has no box convention, but with no `type 1` it needs none — it is a
    # 5x5 Latin square, answerable on rows and columns alone, not a link to
    # refuse.
    payload = _encode(
        {"cells": [{} for _ in range(25)], "size": 5, "constraints": [{"type": 0}]}
    )

    puzzle, _ = decode_link(payload)

    assert puzzle.board == Board(size=5)
    assert all(c.type != "regions-distinct" for c in puzzle.constraints)


def test_shifted_domain_link_decodes_against_its_own_digits() -> None:
    # minDigit/maxDigit set the domain; a 0-based 9x9 reads candidates against
    # 0..8, not 1..9, so bit 0 is a real digit here.
    cells: list[dict[str, object]] = [{} for _ in range(81)]
    cells[0] = {"candidates": _mask({0, 8})}
    payload = _encode(
        {
            "cells": cells,
            "minDigit": 0,
            "maxDigit": 8,
            "constraints": _WIRE_CONSTRAINTS,
        }
    )

    puzzle, state = decode_link(payload)

    assert puzzle.board == Board(size=9, values=range(9))
    assert Candidate("R1C1", frozenset({0, 8})) in state.candidates


@hyp_given(
    size=st.sampled_from([4, 6, 9]),  # a tileable N, so no regions matrix needed
    min_digit=st.integers(min_value=-3, max_value=5),
)
def test_size_and_domain_derivation_round_trip(size: int, min_digit: int) -> None:
    # For any tileable N and any domain start, a size:N link carrying its own
    # minDigit/maxDigit decodes to Board(size=N) over exactly those N digits.
    payload = _encode(
        {
            "cells": [{} for _ in range(size * size)],
            "size": size,
            "minDigit": min_digit,
            "maxDigit": min_digit + size - 1,
            "constraints": [{"type": 0}],
        }
    )

    puzzle, _ = decode_link(payload)

    assert puzzle.board == Board(size=size, values=range(min_digit, min_digit + size))


def _regions_for(n: int, box_rows: int, box_cols: int) -> list[int]:
    """The standard box partition of an n x n board as a flat row-major id
    array, derived independently of the decoder (region = band-row * bands +
    band-col)."""
    bands = n // box_cols
    return [
        (r // box_rows) * bands + (c // box_cols) for r in range(n) for c in range(n)
    ]


def test_non_nine_jigsaw_matrix_rides_onto_constraint_params() -> None:
    # A 6x6 type-1 matrix that isn't the 2x3 convention tiling carries verbatim
    # onto params["regions"] (issue #125 generalized to non-9).
    standard_6 = _regions_for(6, 2, 3)
    # Move R1C1 into R1C4's box (0 -> 1): a real jigsaw, not a within-box swap.
    jigsaw_6 = [standard_6[3], *standard_6[1:]]
    payload = _encode(
        {
            "cells": [{} for _ in range(36)],
            "size": 6,
            "constraints": [{"type": 0}, {"type": 1, "regions": jigsaw_6}],
        }
    )

    puzzle, _ = decode_link(payload)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint.params == {"regions": jigsaw_6}


def test_non_nine_standard_matrix_stays_bare() -> None:
    # A 6x6 type-1 matrix equal to the 2x3 convention tiling emits a bare
    # regions-distinct, just as the classic 9x9 case does.
    payload = _encode(
        {
            "cells": [{} for _ in range(36)],
            "size": 6,
            "constraints": [{"type": 0}, {"type": 1, "regions": _regions_for(6, 2, 3)}],
        }
    )

    puzzle, _ = decode_link(payload)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint == Constraint("regions-distinct")


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


# --- non-9 square-N decode (issue #176) --------------------------------


def test_six_by_six_boxed_link_decodes_at_the_right_size() -> None:
    # A boxed 6x6 ships its 2x3 boxes as an explicit type-1 matrix; a given, a
    # placement, and a center mark land at 6x6 addresses, and the box partition
    # decodes to a bare regions-distinct.
    cells: list[dict[str, object]] = [{} for _ in range(36)]
    cells[0] = {"given": True, "value": 5}  # R1C1
    cells[7] = {"value": 3}  # R2C2
    cells[35] = {"candidates": _mask({2, 4})}  # R6C6
    payload = _encode(
        {
            "cells": cells,
            "size": 6,
            "constraints": [{"type": 0}, {"type": 1, "regions": _regions_for(6, 2, 3)}],
        }
    )

    puzzle, state = decode_link(payload)

    assert puzzle.board == Board(size=6)
    assert puzzle.givens == (Given("R1C1", 5),)
    assert state.places == (Placement("R2C2", 3),)
    assert state.candidates == (Candidate("R6C6", frozenset({2, 4})),)
    assert Constraint("regions-distinct") in puzzle.constraints


def test_four_by_four_link_decodes_at_the_right_size() -> None:
    cells: list[dict[str, object]] = [{} for _ in range(16)]
    cells[15] = {"given": True, "value": 4}  # R4C4
    payload = _encode({"cells": cells, "size": 4, "constraints": [{"type": 0}]})

    puzzle, _ = decode_link(payload)

    assert puzzle.board == Board(size=4)
    assert puzzle.givens == (Given("R4C4", 4),)
