"""The solution-link emitter's pure seam: fill a witness in, re-decode, get it
back out.

`fill_witness` is asserted by round-trip only (never by the intermediate
document shape, per spec #244's testing decision): feed a synthesised
decoded document and a `Witness` through it, re-encode, then `decode_link`
the result and confirm the witness digits come back — singletons as givens,
Schrödinger S-cells as their 2-tuple. `verify_link` is covered end to end on
two tiny synthetic links, one already-solved (found) and one
already-contradictory (broke), so the glue with `decode_link`/`verdict`
is checked without touching the real `links/` corpus.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from verify_links import emit_solution_link, fill_witness, verify_link

from gridfind.layers.board import cell_address
from gridfind.puzzle import (
    Given,
    ModifierDirective,
    SCellPin,
    SingletonPin,
    WorkingState,
)
from gridfind.sudokumaker import decode_link, encode_link
from gridfind.witness import Witness

_WIRE_CONSTRAINTS = [{"type": 0}]


def _document(size: int, *marker_blocks: dict[str, object]) -> dict[str, object]:
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    return {
        "formatVersion": "1.5.0",
        "puzzle": {
            "cells": cells,
            "size": size,
            "constraints": [*_WIRE_CONSTRAINTS, *marker_blocks],
        },
    }


def _marker_block(name: str, index: int) -> dict[str, object]:
    """A `type 2001` marker cage of `name` over the single cell `index` — how a
    real link declares the S-cell or doubler that `fill_witness` then fills, so
    a filled witness round-trips through the same channel the decoder reads."""
    return {"name": name, "type": 2001, "cages": [{"cells": [index]}]}


def _encode(puzzle_data: dict[str, object]) -> str:
    doc = {"formatVersion": "1.5.0", "puzzle": puzzle_data}
    return encode_link(doc)


def _grid(size: int) -> list[list[str]]:
    return [
        [cell_address(r, c) for c in range(1, size + 1)] for r in range(1, size + 1)
    ]


@given(size=st.integers(min_value=2, max_value=5), data=st.data())
def test_fill_witness_round_trips_singleton_digits(
    size: int, data: st.DataObject
) -> None:
    digits = data.draw(
        st.lists(
            st.integers(min_value=1, max_value=size),
            min_size=size * size,
            max_size=size * size,
        )
    )
    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    assignment: dict[str, tuple[int, ...]] = {
        address: (digit,) for address, digit in zip(addresses, digits, strict=True)
    }
    witness = Witness(grid=grid, assignment=assignment, region_map=[])
    document = _document(size)

    filled = fill_witness(document, witness, size)

    url = encode_link(filled)
    puzzle, state = decode_link(url)

    assert state == WorkingState()
    assert set(puzzle.givens) == {
        Given(address, digit[0]) for address, digit in assignment.items()
    }


@given(
    size=st.integers(min_value=2, max_value=5),
    s_cell_index=st.integers(min_value=0),
    data=st.data(),
)
def test_fill_witness_round_trips_a_schrodinger_s_cell(
    size: int, s_cell_index: int, data: st.DataObject
) -> None:
    s_cell_index %= size * size
    domain_max = size + 1  # classic Schrödinger domain: 1..size+1 (k=1 extra digit)
    pair = data.draw(
        st.lists(
            st.integers(min_value=1, max_value=domain_max),
            min_size=2,
            max_size=2,
            unique=True,
        )
    )
    a, b = sorted(pair)

    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    s_cell_address = addresses[s_cell_index]
    assignment: dict[str, tuple[int, ...]] = {
        address: (a, b) if address == s_cell_address else (1,) for address in addresses
    }
    witness = Witness(grid=grid, assignment=assignment, region_map=[])
    document = _document(size, _marker_block("S-cell", s_cell_index))

    filled = fill_witness(document, witness, size)

    url = encode_link(filled)
    puzzle, state = decode_link(url)

    # Every non-S-cell address is a settled digit under a Schrödinger layer,
    # so it round-trips as a singleton pin (spec #348), never a plain given.
    assert SCellPin(s_cell_address, frozenset({a, b})) in state.s_directives
    assert puzzle.givens == ()
    assert {
        SingletonPin(address, digit[0])
        for address, digit in assignment.items()
        if address != s_cell_address
    } <= set(state.s_directives)


def test_fill_witness_marks_a_modifier_cell_as_a_doubler() -> None:
    # A cell the solver found to be a modifier round-trips as a doubler: the
    # source link's `Doubler` marker cage declares the cell, and the filled
    # witness decodes back to its modifier directive. Cells the witness never
    # flagged stay ordinary givens.
    size = 4
    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    modifier_index = 6
    modifier_address = addresses[modifier_index]
    witness = Witness(
        grid=grid,
        assignment=dict.fromkeys(addresses, (1,)),
        region_map=[],
        modifiers={modifier_address: "doubler"},
    )

    document = _document(size, _marker_block("Doubler", modifier_index))
    filled = fill_witness(document, witness, size)

    _, state = decode_link(encode_link(filled))
    assert state.modifier_directives == (
        ModifierDirective(modifier_address, is_modifier=True),
    )


def test_verify_link_reports_a_solution_link_for_a_found_case() -> None:
    # A fully-given, already-valid 2x2 Latin square: rows {1,2}/{2,1},
    # columns {1,2}/{2,1} — trivially found, so filling in the witness
    # reproduces the same givens verbatim.
    cells = [
        {"given": True, "value": 1},
        {"given": True, "value": 2},
        {"given": True, "value": 2},
        {"given": True, "value": 1},
    ]
    link = _encode({"cells": cells, "size": 2, "constraints": _WIRE_CONSTRAINTS})

    solution_link = verify_link([link])

    assert solution_link.startswith("https://sudokumaker.app/?puzzle=")
    puzzle, state = decode_link(solution_link)
    assert state == WorkingState()
    assert set(puzzle.givens) == {
        Given("R1C1", 1),
        Given("R1C2", 2),
        Given("R2C1", 2),
        Given("R2C2", 1),
    }


def test_verify_link_reports_broke_for_a_broke_case() -> None:
    # Two givens in the same row share a digit — contradicts rows-distinct
    # before any search is needed.
    cells = [
        {"given": True, "value": 1},
        {"given": True, "value": 1},
        {},
        {},
    ]
    link = _encode({"cells": cells, "size": 2, "constraints": _WIRE_CONSTRAINTS})

    assert verify_link([link]) == "broke"


def test_emit_solution_link_stamps_the_board_size() -> None:
    # A source document that omits `size`: the emitted solution link must carry
    # the known board size, or it would open at SudokuMaker's 9x9 default. A
    # sizeless link does not decode (ADR-0011), so a stamped size is what lets
    # `decode_link` recover this 2x2 at all.
    size = 2
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    link = _encode({"cells": cells, "constraints": _WIRE_CONSTRAINTS})  # no size
    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    witness = Witness(
        grid=grid,
        assignment=dict.fromkeys(addresses, (1,)),
        region_map=[],
    )

    solution = emit_solution_link(link, witness, size)

    puzzle, _ = decode_link(solution)
    assert puzzle.board.size == size


# A 4x4 board's 2x2 boxes as a type-1 regions matrix, row-major.
_REGIONS_4X4 = [(i // 4 // 2) * 2 + (i % 4 // 2) for i in range(16)]


def _doubler_cage_link(*, doubler: bool) -> str:
    """A fully-given valid 4x4 Latin square with a killer cage summing
    R1C1+R1C2 to 4. With a `Doubler` marker cage over R1C1 its digit counts
    twice, 2·1+2=4, satisfying the cage (found); without it the cage sums the
    raw givens, 1+2=3 ≠ 4 (broke). So marker presence flips broke↔found, and
    `verify_link` must decode the marker to report the right one."""
    rows = [[1, 2, 3, 4], [3, 4, 1, 2], [2, 1, 4, 3], [4, 3, 2, 1]]
    cells: list[dict[str, object]] = [
        {"given": True, "value": digit} for row in rows for digit in row
    ]
    constraints: list[dict[str, object]] = [
        {"type": 0},
        {"type": 1, "regions": _REGIONS_4X4},
        {"type": 301, "cages": [{"cells": [0, 1], "value": 4}]},
    ]
    if doubler:
        constraints.append(_marker_block("Doubler", 0))
    return _encode({"cells": cells, "size": 4, "constraints": constraints})


def test_verify_link_decodes_a_doubler_marker() -> None:
    # Without the marker the cage sums the raw givens, 1+2=3 ≠ 4: broke.
    assert verify_link([_doubler_cage_link(doubler=False)]) == "broke"

    # With the marker R1C1's digit counts twice, 2·1+2=4: found, so the
    # emitter reports a solution-link rather than `broke`.
    solution_link = verify_link([_doubler_cage_link(doubler=True)])
    assert solution_link.startswith("https://sudokumaker.app/?puzzle=")
