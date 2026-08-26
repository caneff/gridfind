"""`cells`: one grid cell decoded to its directives, and the wire-write inverse.

`decode_cell` turns a single wire cell into the given/placement/candidate it
carries; `write_cell` is its inverse for the re-encoder; `_parse_scell_value`
reads the S-cell marker's own `value` string into 0, 1, or 2 digits — a
module-private parse seam, imported from beside the test rather than through
the package door.
"""

import pytest
from hypothesis import given as hyp_given
from hypothesis import strategies as st

from gridfind.puzzle import (
    Candidate,
    Given,
    Placement,
    WorkingState,
)
from gridfind.sudokumaker import link_to_puzzle, write_cell
from gridfind.sudokumaker.cells import CellDecode, _parse_scell_value, decode_cell
from gridfind.sudokumaker.conftest import (
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    encode_document,
)


def test_write_cell_writes_a_singleton_as_a_placement_on_a_non_given_cell() -> None:
    # write_cell is the one wire-write seam: a length-1 content on a cell that
    # was not a given in the source document is a solved placement, not a
    # given — the setter's givens and the rules' placements must stay tellable
    # apart on the solution pane (#725).
    cell: dict[str, object] = {}
    write_cell(cell, (5,))
    assert cell == {"value": 5}


def test_write_cell_keeps_a_given_cell_a_given() -> None:
    # A cell the source document already marked as a given stays a given after
    # the witness fill, even though the digit is rewritten.
    cell: dict[str, object] = {"given": True, "value": 1}
    write_cell(cell, (5,))
    assert cell == {"given": True, "value": 5}


def test_write_cell_writes_a_schrodinger_pair_as_two_center_marks() -> None:
    # A length-2 content is an S-cell: write_cell sets the two center marks
    # (candidates) and no color bit — SudokuMaker's cosmetic display of the
    # pair, while the decode-time pair rides the marker cage's value.
    cell: dict[str, object] = {}
    write_cell(cell, (2, 7))
    assert cell == {"candidates": (1 << 2) | (1 << 7)}


@pytest.mark.parametrize(
    ("cell", "domain", "expected"),
    [
        (
            {"given": True, "value": 5},
            range(1, 10),
            CellDecode(givens=(Given("R1C1", 5),)),
        ),
        (
            {"value": 5},
            range(1, 10),
            CellDecode(places=(Placement("R1C1", 5),)),
        ),
        (
            {"candidates": (1 << 2) | (1 << 5)},
            range(1, 10),
            CellDecode(candidates=(Candidate("R1C1", frozenset({2, 5})),)),
        ),
        ({}, range(1, 10), CellDecode()),
    ],
    ids=["given", "placement", "candidate", "empty"],
)
def test_decode_cell_returns_one_cells_directives(
    cell: dict[str, object],
    domain: range,
    expected: CellDecode,
) -> None:
    # decode_cell is the one home for per-cell decode: it returns the directives
    # a single cell yields as one value. A non-marker cell decodes its plain
    # given/placement/candidate; the S-cell marker path is covered in markers.
    assert decode_cell(cell, "R1C1", domain) == expected


def test_colors_and_corner_marks_leave_the_state_empty() -> None:
    # Notations gridfind can't represent — a cell color and a corner mark — must
    # contribute nothing, so a cosmetic mark never corrupts the verdict.
    cells = [{} for _ in range(81)]
    cells[0] = {"colors": [1]}
    cells[1] = {"cornerPencilMarks": 8}
    payload = encode_document({"cells": cells, "constraints": WIRE_CONSTRAINTS})

    _, state = link_to_puzzle(payload)

    assert state == WorkingState()


def test_settled_value_on_a_non_schrodinger_puzzle_stays_given_or_placement() -> None:
    # No S-axis exists without a schrodinger layer, so on an ordinary puzzle a
    # settled given/placement stays a plain given/placement (ADR-0014).
    cells = list(EMPTY_CELLS)
    cells[0] = {"given": True, "value": 7}
    cells[1] = {"value": 3}
    payload = encode_document({"cells": cells, "constraints": WIRE_CONSTRAINTS})

    puzzle, state = link_to_puzzle(payload)

    assert puzzle.givens == (Given("R1C1", 7),)
    assert state.places == (Placement("R1C2", 3),)
    assert state.s_directives == ()


@hyp_given(text=st.text(max_size=12))
def test_scell_value_parser_never_crashes_on_arbitrary_text(text: str) -> None:
    # The parser (ADR-0014) handles any garbage a link's `value` could carry
    # without raising, always yielding 0, 1, or 2 digits. It does not enforce
    # the board's domain — an out-of-domain digit rides through for the
    # verdict-time guard to refuse — so this asserts shape, not membership.
    domain = range(10)

    digits = _parse_scell_value(text, domain)

    assert len(digits) in (0, 1, 2)


@hyp_given(
    a=st.integers(min_value=0, max_value=9), b=st.integers(min_value=0, max_value=9)
)
def test_scell_value_parser_comma_form_round_trips_any_pair(a: int, b: int) -> None:
    domain = range(10)

    digits = _parse_scell_value(f"{a},{b}", domain)

    assert digits == (a, b)
