"""`boundary`: the link's outer envelope and its size/domain derivation.

`decode_document`/`encode_link` are the compress/decompress door; `_board_size`,
`_digit_domain`, and `_schrodinger_domain` read the grid's shape and digit range
off the raw puzzle block. These are exercised through `decode_link` where a real
link is the honest input, and directly where the helper's own edge cases (the
Schrödinger domain's default and explicit `minDigit`) are the point.
"""

import json

import pytest
from hypothesis import given as hyp_given
from hypothesis import strategies as st
from lzstring import LZString

from gridfind.puzzle import (
    Board,
    Candidate,
    Given,
    Placement,
    Puzzle,
    WorkingState,
)
from gridfind.sudokumaker import decode_document, decode_link, encode_link
from gridfind.sudokumaker.boundary import _enabled_blocks, _schrodinger_domain
from gridfind.sudokumaker.conftest import (
    CLASSIC_CONSTRAINTS,
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    encode_document,
    mask,
    regions_for,
)


def test_encode_link_round_trips_a_classic_document() -> None:
    cells: list[dict[str, object]] = [{} for _ in range(81)]
    cells[0] = {"given": True, "value": 7}
    document: dict[str, object] = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "constraints": WIRE_CONSTRAINTS},
    }

    url = encode_link(document)

    # Exact reverse of decode_link's payload step: the emitted link's own
    # payload decompresses back to the identical document it was given.
    payload = url.split("?puzzle=", 1)[-1]
    raw = LZString.decompressFromEncodedURIComponent(payload)
    assert json.loads(raw) == document
    # size/type survive the round trip: the emitted link opens as the same
    # classic 9x9 puzzle+state decode_link would read from the document.
    puzzle, state = decode_link(url)
    assert puzzle == Puzzle(
        board=Board(size=9),
        constraints=CLASSIC_CONSTRAINTS,
        givens=(Given("R1C1", 7),),
    )
    assert state == WorkingState()


def test_decode_document_is_the_inverse_of_encode_link() -> None:
    # decode_document returns the whole document — formatVersion plus the
    # puzzle block — so a document survives encode_link then decode_document
    # unchanged. decode_link keeps only the puzzle block; this is the seam a
    # re-encoder needs to preserve every field the app renders.
    cells: list[dict[str, object]] = [{} for _ in range(81)]
    cells[0] = {"given": True, "value": 7}
    document: dict[str, object] = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "constraints": WIRE_CONSTRAINTS},
    }

    assert decode_document(encode_link(document)) == document


@pytest.mark.parametrize(
    ("puzzle", "match"),
    [
        (
            {"cells": [{} for _ in range(80)], "constraints": WIRE_CONSTRAINTS},
            "do not match size",
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
            {"cells": EMPTY_CELLS, "size": 6, "constraints": [{"type": 0}]},
            "do not match size",
        ),
        # No size at all: an absent size defaults to the classic 9x9 (ADR-0011),
        # not isqrt(16)=4, so a 16-cell link is malformed rather than a 4x4.
        (
            {"cells": [{} for _ in range(16)], "constraints": [{"type": 0}]},
            "do not match size",
        ),
        # A domain that doesn't span the board: 0..5 is six digits for a 9x9.
        (
            {
                "cells": EMPTY_CELLS,
                "minDigit": 0,
                "maxDigit": 5,
                "constraints": WIRE_CONSTRAINTS,
            },
            "is not 9 digits",
        ),
    ],
    ids=[
        "wrong-cell-count",
        "non-square",
        "size-mismatch",
        "sizeless-non-classic-count",
        "bad-domain-span",
    ],
)
def test_non_classic_link_is_rejected(puzzle: dict[str, object], match: str) -> None:
    # Each case fails for *its own* reason, not an incidental ValueError.
    with pytest.raises(ValueError, match=match):
        decode_link(encode_document(puzzle))


def test_shifted_domain_link_decodes_against_its_own_digits() -> None:
    # minDigit/maxDigit set the domain; a 0-based 9x9 reads candidates against
    # 0..8, not 1..9, so bit 0 is a real digit here.
    cells: list[dict[str, object]] = [{} for _ in range(81)]
    cells[0] = {"candidates": mask({0, 8})}
    payload = encode_document(
        {
            "cells": cells,
            "minDigit": 0,
            "maxDigit": 8,
            "constraints": WIRE_CONSTRAINTS,
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
    payload = encode_document(
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


def test_six_by_six_boxed_link_decodes_at_the_right_size() -> None:
    # A boxed 6x6 ships its 2x3 boxes as an explicit type-1 matrix; a given, a
    # placement, and a center mark land at 6x6 addresses, and the box partition
    # decodes to a bare regions-distinct.
    cells: list[dict[str, object]] = [{} for _ in range(36)]
    cells[0] = {"given": True, "value": 5}  # R1C1
    cells[7] = {"value": 3}  # R2C2
    cells[35] = {"candidates": mask({2, 4})}  # R6C6
    payload = encode_document(
        {
            "cells": cells,
            "size": 6,
            "constraints": [{"type": 0}, {"type": 1, "regions": regions_for(6, 2, 3)}],
        }
    )

    puzzle, state = decode_link(payload)

    assert puzzle.board == Board(size=6)
    assert puzzle.givens == (Given("R1C1", 5),)
    assert state.places == (Placement("R2C2", 3),)
    assert state.candidates == (Candidate("R6C6", frozenset({2, 4})),)


def test_four_by_four_link_decodes_at_the_right_size() -> None:
    cells: list[dict[str, object]] = [{} for _ in range(16)]
    cells[15] = {"given": True, "value": 4}  # R4C4
    payload = encode_document({"cells": cells, "size": 4, "constraints": [{"type": 0}]})

    puzzle, _ = decode_link(payload)

    assert puzzle.board == Board(size=4)
    assert puzzle.givens == (Given("R4C4", 4),)


@pytest.mark.parametrize(
    ("puzzle_data", "expected"),
    [
        # Default: the widening digit is 0, so a 9-board's S-domain is 0..9.
        ({}, range(10)),
        # An explicit minDigit is honored as-is, so a setter who wants the
        # classic 1..N+1 span may ask for it (ADR-0014).
        ({"minDigit": 1}, range(1, 11)),
    ],
    ids=["default-zero", "explicit-min-digit"],
)
def test_schrodinger_domain_widens_by_one_honoring_min_digit(
    puzzle_data: dict[str, object], expected: range
) -> None:
    assert _schrodinger_domain(puzzle_data, 9) == expected


def test_enabled_blocks_yields_only_enabled_blocks_of_the_asked_type() -> None:
    # The shared enablement filter every per-type decoder iterates behind: it
    # yields the blocks of one type in wire order, and folds the three guards —
    # a disabled block is skipped (the setter switched it off), a block of
    # another type is skipped, and a non-dict block is ignored.
    puzzle_data: dict[str, object] = {
        "constraints": [
            {"type": 300, "id": "first"},
            {"type": 301, "id": "other-type"},
            {"type": 300, "id": "disabled", "disabled": True},
            "not-a-dict",
            {"type": 300, "id": "second"},
        ]
    }

    kept = [block["id"] for block in _enabled_blocks(puzzle_data, 300)]

    assert kept == ["first", "second"]


def test_enabled_blocks_yields_nothing_when_constraints_is_not_a_list() -> None:
    assert list(_enabled_blocks({"constraints": "bad"}, 300)) == []
