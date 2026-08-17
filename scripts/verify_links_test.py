"""The solution-link emitter's pure seam: fill a witness in, re-decode, get it
back out.

`fill_witness` is asserted by round-trip only (never by the intermediate
document shape): feed a synthesised
decoded document and a `Witness` through it, re-encode, then `link_to_puzzle`
the result and confirm the witness digits come back — singletons as givens,
Schrödinger S-cells as their 2-tuple. `verify_link` is covered end to end on
two tiny synthetic links, one already-solved (found) and one
already-contradictory (broke), so the glue with `link_to_puzzle`/`verdict`
is checked without touching the real `links/` corpus.
"""

from __future__ import annotations

from typing import Any, cast

from hypothesis import given
from hypothesis import strategies as st
from verify_links import emit_solution_link, fill_witness, verify_link

from gridfind.cell_geometry import format_address
from gridfind.layers.regions import RegionMap
from gridfind.puzzle import Given, ModifierDirective, WorkingState
from gridfind.s_directives import SCellPin, SingletonPin
from gridfind.sudokumaker import (
    document_to_link,
    link_to_document,
    link_to_puzzle,
)
from gridfind.sudokumaker.markers import _MARKER_COLOR_PALETTE
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
    return document_to_link(doc)


def _grid(size: int) -> list[list[str]]:
    return [
        [format_address(r, c) for c in range(1, size + 1)] for r in range(1, size + 1)
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
    witness = Witness(grid=grid, assignment=assignment, region_map=RegionMap([]))
    document = _document(size)

    filled = fill_witness(document, witness, size)

    url = document_to_link(filled)
    puzzle, state = link_to_puzzle(url)

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
    witness = Witness(grid=grid, assignment=assignment, region_map=RegionMap([]))
    document = _document(size, _marker_block("S-cell", s_cell_index))

    filled = fill_witness(document, witness, size)

    url = document_to_link(filled)
    puzzle, state = link_to_puzzle(url)

    # Every non-S-cell address is a settled digit under a Schrödinger layer,
    # so it round-trips as a singleton pin, never a plain given.
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
        region_map=RegionMap([]),
        modifiers={modifier_address: "doubler"},
    )

    document = _document(size, _marker_block("Doubler", modifier_index))
    filled = fill_witness(document, witness, size)

    _, state = link_to_puzzle(document_to_link(filled))
    assert state.modifier_directives == (
        ModifierDirective(modifier_address, is_modifier=True),
    )


def test_fill_witness_cages_a_discovered_s_cell() -> None:
    # The solver discovers S-cells the source link never declared. `fill_witness`
    # marks each by cage, so an S-cell the marker block did not name still
    # round-trips as a pin — mark by cage, never by color.
    size = 4
    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    declared, discovered = 0, 5
    assignment: dict[str, tuple[int, ...]] = {
        address: (1, 2) if index in (declared, discovered) else (1,)
        for index, address in enumerate(addresses)
    }
    witness = Witness(grid=grid, assignment=assignment, region_map=RegionMap([]))
    document = _document(size, _marker_block("S-cell", declared))

    filled = fill_witness(document, witness, size)

    _, state = link_to_puzzle(document_to_link(filled))
    pinned = {pin.address for pin in state.s_directives if isinstance(pin, SCellPin)}
    assert {addresses[declared], addresses[discovered]} <= pinned


def test_fill_witness_folds_a_discovered_doubler_into_the_cage() -> None:
    # A doubler the solver found but the source link never declared is folded
    # into the `Doubler` cage, so every modifier cell is marked by cage.
    size = 4
    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    declared, discovered = 6, 9
    witness = Witness(
        grid=grid,
        assignment=dict.fromkeys(addresses, (1,)),
        region_map=RegionMap([]),
        modifiers={addresses[declared]: "doubler", addresses[discovered]: "doubler"},
    )
    document = _document(size, _marker_block("Doubler", declared))

    filled = fill_witness(document, witness, size)

    _, state = link_to_puzzle(document_to_link(filled))
    assert set(state.modifier_directives) == {
        ModifierDirective(addresses[declared], is_modifier=True),
        ModifierDirective(addresses[discovered], is_modifier=True),
    }


def test_fill_witness_folds_a_discovered_constant_into_the_cage() -> None:
    # A constant modifier the solver found but the source link never declared is
    # folded into the `Constant` cage, so every modifier cell is marked by cage —
    # the same discovery path as the doubler, routed through `cosmetic_cage_kind`.
    size = 4
    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    declared, discovered = 6, 9
    witness = Witness(
        grid=grid,
        assignment=dict.fromkeys(addresses, (1,)),
        region_map=RegionMap([]),
        modifiers={addresses[declared]: "constant", addresses[discovered]: "constant"},
    )
    document = _document(size, _marker_block("Constant 5", declared))

    filled = fill_witness(document, witness, size)

    _, state = link_to_puzzle(document_to_link(filled))
    assert set(state.modifier_directives) == {
        ModifierDirective(addresses[declared], is_modifier=True),
        ModifierDirective(addresses[discovered], is_modifier=True),
    }


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
    puzzle, state = link_to_puzzle(solution_link)
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
    # `link_to_puzzle` recover this 2x2 at all.
    size = 2
    cells: list[dict[str, object]] = [{} for _ in range(size * size)]
    link = _encode({"cells": cells, "constraints": _WIRE_CONSTRAINTS})
    grid = _grid(size)
    addresses = [address for row in grid for address in row]
    witness = Witness(
        grid=grid,
        assignment=dict.fromkeys(addresses, (1,)),
        region_map=RegionMap([]),
    )

    solution = emit_solution_link(link, witness, size)

    puzzle, _ = link_to_puzzle(solution)
    assert puzzle.board.size == size


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


def test_emit_solution_link_colors_the_doubler_marker_cage() -> None:
    # The emitted solution link is the one surface the eval slideshow's right
    # pane renders, so its Doubler block must carry the lone-type red the
    # reviewer expects to see, with the ordinary killer cage untouched.
    solution_link = verify_link([_doubler_cage_link(doubler=True)])

    document = link_to_document(solution_link)
    puzzle_data = cast("dict[str, Any]", document["puzzle"])
    constraints = cast("list[dict[str, Any]]", puzzle_data["constraints"])
    doubler_block = next(c for c in constraints if c.get("name") == "Doubler")
    killer_block = next(c for c in constraints if c.get("type") == 301)

    assert doubler_block["style"]["cage"]["color"] == _MARKER_COLOR_PALETTE[0]
    assert "style" not in killer_block
