"""The SudokuMaker decoder at its one seam: `decode_link(link) -> Puzzle, state`.

The positive fixture is the real classic link (research §4a):
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
    ModifierDirective,
    Placement,
    Puzzle,
    SCellPin,
    SingletonPin,
    WorkingState,
)
from gridfind.sudokumaker import (
    _RED_BIT,
    LinkVariant,
    _CellDecode,
    _decode_cell,
    _edge_to_pair,
    decode_document,
    decode_link,
    encode_link,
    write_cell,
)

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
    # R6C8's single center mark `candidates 4 = 2^2` is a one-digit narrowing,
    # so it lands as a Candidate, never a Placement — the exact-state equality
    # below pins that (R6C8 is in candidates and absent from places).
    assert state == WorkingState(
        places=(Placement("R1C1", 7),),
        candidates=(
            Candidate("R2C9", frozenset({1, 2, 9})),
            Candidate("R6C8", frozenset({2})),
        ),
    )


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


def test_encode_link_round_trips_a_classic_document() -> None:
    cells: list[dict[str, object]] = [{} for _ in range(81)]
    cells[0] = {"given": True, "value": 7}
    document: dict[str, object] = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "constraints": _WIRE_CONSTRAINTS},
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
        constraints=_CLASSIC_CONSTRAINTS,
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
        "puzzle": {"cells": cells, "constraints": _WIRE_CONSTRAINTS},
    }

    assert decode_document(encode_link(document)) == document


def test_write_cell_writes_a_singleton_as_a_given() -> None:
    # write_cell is the one wire-write seam: a length-1 content is a plain given
    # the classic decode reads straight back.
    cell: dict[str, object] = {}
    write_cell(cell, (5,))
    assert cell == {"given": True, "value": 5}


def test_write_cell_round_trips_a_schrodinger_pin() -> None:
    # A length-2 content is an S-cell pin: write_cell sets the red bit and the
    # two center marks, so decoding under --schrodinger returns that pin — the
    # inverse of the decoder's SCellPin branch, singleton and pair through one
    # door.
    cells = list(_EMPTY_CELLS)
    cell: dict[str, object] = {}
    write_cell(cell, (2, 7))
    cells[0] = cell
    payload = _schrodinger_link(cells)

    _, state = decode_link(payload, LinkVariant(schrodinger=True))

    assert SCellPin("R1C1", frozenset({2, 7})) in state.s_directives


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
        # No size at all: an absent size defaults to the classic 9x9 (ADR-0011),
        # not isqrt(16)=4, so a 16-cell link is malformed rather than a 4x4.
        (
            {"cells": [{} for _ in range(16)], "constraints": [{"type": 0}]},
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
        "non-square",
        "size-mismatch",
        "sizeless-non-classic-count",
        "bad-domain-span",
    ],
)
def test_non_classic_link_is_rejected(puzzle: dict[str, object], match: str) -> None:
    # Each case fails for *its own* reason, not an incidental ValueError.
    with pytest.raises(ValueError, match=match):
        decode_link(_encode(puzzle))


def test_inert_unmodeled_constraints_decode_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A real link routinely carries cosmetic or empty extras: an
    # empty unmodeled clue list, cosmetic pen-lines, an empty group. None
    # emits a rule, so the puzzle is identical to one without them and
    # nothing warns.
    with_extras = _encode(
        {
            "cells": _EMPTY_CELLS,
            "constraints": [
                *_WIRE_CONSTRAINTS,
                {"type": 250, "clues": []},  # empty, unmodeled clue list
                {"type": 2000, "lines": [[0, 1]]},  # cosmetic pen-lines
                {"type": 303, "input": {"groups": [{"cells": []}]}},  # empty group
            ],
        }
    )
    plain = _encode({"cells": _EMPTY_CELLS, "constraints": _WIRE_CONSTRAINTS})

    puzzle_extras, state_extras = decode_link(with_extras)
    puzzle_plain, state_plain = decode_link(plain)

    assert puzzle_extras == puzzle_plain
    assert state_extras == state_plain
    assert capsys.readouterr().err == ""


def test_active_unmodeled_constraint_decodes_with_named_stderr_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A constraint carrying live data is dropped, not rejected: the verdict is
    # the reduced-ruleset answer, stderr names the dropped constraint (its
    # `definition.name` and type) so the drop is never silent, and stdout (the
    # verdict channel) is untouched.
    payload = _encode(
        {
            "cells": _EMPTY_CELLS,
            "constraints": [
                *_WIRE_CONSTRAINTS,
                {
                    "type": 1000,
                    "clues": [{"cell": 0}],
                    "definition": {"name": "Same Difference Lines"},
                },
            ],
        }
    )

    puzzle, _ = decode_link(payload)

    captured = capsys.readouterr()
    assert puzzle.constraints == _CLASSIC_CONSTRAINTS
    assert "Same Difference Lines" in captured.err
    assert "1000" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "live_payload",
    [
        {"clues": [{"cell": 0}]},
        {"negative": [1]},
        {"input": {"groups": [{"cells": [0, 1]}]}},
        {"cages": [{"cells": [0, 1], "value": 5}]},
    ],
    ids=["clues", "negative", "input-groups", "cages"],
)
def test_every_live_payload_shape_warns(
    live_payload: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    # Live data reaches gridfind under any of four shapes; each must trip the
    # loud drop, matching scripts/inspect_link.py's classification.
    payload = _encode(
        {
            "cells": _EMPTY_CELLS,
            "constraints": [*_WIRE_CONSTRAINTS, {"type": 1000, **live_payload}],
        }
    )

    decode_link(payload)

    assert "1000" in capsys.readouterr().err


def test_disabled_active_constraint_is_skipped_without_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A disabled constraint is one the setter switched off — skipped before the
    # active/inert check, so even a live payload never warns.
    payload = _encode(
        {
            "cells": _EMPTY_CELLS,
            "constraints": [
                *_WIRE_CONSTRAINTS,
                {"type": 1000, "clues": [{"cell": 0}], "disabled": True},
            ],
        }
    )

    decode_link(payload)

    assert capsys.readouterr().err == ""


def test_link_without_type_one_is_a_latin_square() -> None:
    # No `type 1` regions block means the setter asked for no regions — rows and
    # columns distinct only. gridfind must not invent boxes (the box tiling is
    # supplied only when the link carries the box matrix). A real boxed
    # SudokuMaker puzzle always ships its boxes as an explicit `type 1`.
    payload = _encode({"cells": _EMPTY_CELLS, "constraints": [{"type": 0}]})

    puzzle, _ = decode_link(payload)

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
    # onto params["regions"] (generalized to non-9).
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
    # A type 1 link whose regions differ from the standard 3x3 partition decodes
    # with the setter's own matrix carried on the regions-distinct constraint's
    # params.
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


# --- --schrodinger ingest ---------------------------------

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

    puzzle, _ = decode_link(payload, LinkVariant(schrodinger=True, reading="classic"))

    assert puzzle.board == Board(size=9, values=range(10))
    assert Constraint("schrodinger") in puzzle.constraints


def test_schrodinger_link_ignores_cosmetic_and_disabled_constraints() -> None:
    # The real link's 13 constraints include cosmetic types the classic-only
    # guard would otherwise reject outright, plus a disabled duplicate of the
    # regions matrix — both ignored under --schrodinger.
    payload = _schrodinger_link(_EMPTY_CELLS)

    puzzle, _ = decode_link(payload, LinkVariant(schrodinger=True))

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint == Constraint("regions-distinct")


def test_schrodinger_min_digit_defaults_to_one_when_absent() -> None:
    payload = _encode(
        {"cells": _EMPTY_CELLS, "constraints": _SCHRODINGER_WIRE_CONSTRAINTS}
    )

    puzzle, _ = decode_link(payload, LinkVariant(schrodinger=True))

    assert puzzle.board.values == range(1, 11)


def test_unsupported_reading_is_refused() -> None:
    payload = _schrodinger_link(_EMPTY_CELLS)

    with pytest.raises(ValueError, match="reading"):
        decode_link(payload, LinkVariant(schrodinger=True, reading="sum-valued"))


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

    puzzle, state = decode_link(payload, LinkVariant(schrodinger=True))

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
        decode_link(payload, LinkVariant(schrodinger=True))


# --- non-9 square-N decode --------------------------------


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


# --- edge -> pair -----------------------------


@pytest.mark.parametrize(
    ("edge", "expected"),
    [
        (70, ("R4C8", "R5C8")),
        (103, ("R6C5", "R7C5")),
        (75, ("R5C3", "R5C4")),
        (132, ("R8C6", "R8C7")),
    ],
    ids=["x-vertical", "v-vertical", "kropki-horizontal-75", "kropki-horizontal-132"],
)
def test_edge_to_pair_oracle_cases(edge: int, expected: tuple[str, str]) -> None:
    # Verified against a real link during design: all four fit the two
    # closed-form formulas exactly on a 9x9 board.
    assert _edge_to_pair(edge, size=9) == expected


def _parse_address(address: str) -> tuple[int, int]:
    row, _, col = address[1:].partition("C")
    return int(row), int(col)


@st.composite
def _valid_edges(draw: st.DrawFn) -> tuple[int, int, str]:
    """A `(size, edge, orientation)` triple where `edge` is a real,
    in-bounds edge of that orientation on a `size`x`size` board — built from
    the same `r0, c0` space `_edge_to_pair` inverts, so every draw is valid
    by construction."""
    size = draw(st.integers(min_value=2, max_value=15))
    orientation = draw(st.sampled_from(["horizontal", "vertical"]))
    if orientation == "horizontal":
        r0 = draw(st.integers(min_value=0, max_value=size - 1))
        c0 = draw(st.integers(min_value=0, max_value=size - 2))
        edge = 2 * size * r0 + c0 + 1
    else:
        r0 = draw(st.integers(min_value=0, max_value=size - 2))
        c0 = draw(st.integers(min_value=0, max_value=size - 1))
        edge = 2 * size * r0 + c0 + size
    return size, edge, orientation


@hyp_given(_valid_edges())
def test_edge_to_pair_decodes_an_in_bounds_adjacent_pair(
    case: tuple[int, int, str],
) -> None:
    size, edge, orientation = case
    a, b = _edge_to_pair(edge, size)
    row_a, col_a = _parse_address(a)
    row_b, col_b = _parse_address(b)

    assert 1 <= row_a <= size
    assert 1 <= col_a <= size
    assert 1 <= row_b <= size
    assert 1 <= col_b <= size
    if orientation == "horizontal":
        assert row_a == row_b
        assert col_b == col_a + 1
    else:
        assert col_a == col_b
        assert row_b == row_a + 1


def test_edge_to_pair_rejects_an_out_of_bounds_edge() -> None:
    # size=2's only edges are 0..7; 8 names no in-bounds pair.
    with pytest.raises(ValueError, match="edge"):
        _edge_to_pair(8, size=2)


# --- type 202 XV decode -----------------------


def _constraint_link(constraint: dict[str, object]) -> str:
    return _encode(
        {"cells": _EMPTY_CELLS, "constraints": [*_WIRE_CONSTRAINTS, constraint]}
    )


@pytest.mark.parametrize(
    ("value", "edge", "alias", "cells"),
    [
        (10, 70, "x", ["R4C8", "R5C8"]),
        (5, 103, "v", ["R6C5", "R7C5"]),
        (10, 75, "x", ["R5C3", "R5C4"]),
    ],
    ids=["x-vertical", "v-vertical", "x-horizontal"],
)
def test_xv_clue_decodes_to_aliased_group_sum(
    value: int, edge: int, alias: str, cells: list[str]
) -> None:
    payload = _constraint_link({"type": 202, "clues": [{"value": value, "edge": edge}]})

    puzzle, _ = decode_link(payload)

    assert Constraint(alias, params={"cells": cells}) in puzzle.constraints


def test_multiple_xv_clues_each_decode_to_their_own_constraint() -> None:
    payload = _constraint_link(
        {
            "type": 202,
            "clues": [{"value": 10, "edge": 70}, {"value": 5, "edge": 103}],
        }
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("x", params={"cells": ["R4C8", "R5C8"]}) in puzzle.constraints
    assert Constraint("v", params={"cells": ["R6C5", "R7C5"]}) in puzzle.constraints


def test_xv_negative_list_warns_but_keeps_positive_clues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _constraint_link(
        {"type": 202, "clues": [{"value": 10, "edge": 70}], "negative": [1, 2]}
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("x", params={"cells": ["R4C8", "R5C8"]}) in puzzle.constraints
    assert "negative" in capsys.readouterr().err


def test_xv_value_that_is_neither_x_nor_v_is_refused() -> None:
    # X (10) and V (5) are the only XV sums; any other labelled value names no
    # alias, so the link is refused rather than modeled as a wrong sum.
    payload = _constraint_link({"type": 202, "clues": [{"value": 7, "edge": 70}]})

    with pytest.raises(ValueError, match="neither"):
        decode_link(payload)


# --- type 200 white-kropki decode --------------


@pytest.mark.parametrize(
    ("value", "edge", "cells"),
    [
        (1, 75, ["R5C3", "R5C4"]),
        (1, 132, ["R8C6", "R8C7"]),
        (1, 70, ["R4C8", "R5C8"]),
    ],
    ids=["white-horizontal-75", "white-horizontal-132", "white-vertical-70"],
)
def test_kropki_clue_decodes_to_pair_difference(
    value: int, edge: int, cells: list[str]
) -> None:
    payload = _constraint_link({"type": 200, "clues": [{"value": value, "edge": edge}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": cells, "diff": value})
        in puzzle.constraints
    )


def test_kropki_honors_a_labelled_non_one_value() -> None:
    # A white dot labelled with a difference other than 1 is honored verbatim —
    # never silently treated as the consecutive (diff 1) default.
    payload = _constraint_link({"type": 200, "clues": [{"value": 3, "edge": 75}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 3})
        in puzzle.constraints
    )


def test_multiple_kropki_clues_each_decode_to_their_own_constraint() -> None:
    payload = _constraint_link(
        {
            "type": 200,
            "clues": [{"value": 1, "edge": 75}, {"value": 1, "edge": 132}],
        }
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 1})
        in puzzle.constraints
    )
    assert (
        Constraint("pair-difference", params={"cells": ["R8C6", "R8C7"], "diff": 1})
        in puzzle.constraints
    )


def test_kropki_negative_list_warns_but_keeps_positive_clues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _constraint_link(
        {"type": 200, "clues": [{"value": 1, "edge": 75}], "negative": [1, 2]}
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-difference", params={"cells": ["R5C3", "R5C4"], "diff": 1})
        in puzzle.constraints
    )
    assert "negative" in capsys.readouterr().err


# --- type 201 black-kropki decode ----------------


@pytest.mark.parametrize(
    ("value", "edge", "cells"),
    [
        (2, 75, ["R5C3", "R5C4"]),
        (2, 132, ["R8C6", "R8C7"]),
        (2, 70, ["R4C8", "R5C8"]),
    ],
    ids=["black-horizontal-75", "black-horizontal-132", "black-vertical-70"],
)
def test_black_kropki_clue_decodes_to_pair_ratio(
    value: int, edge: int, cells: list[str]
) -> None:
    payload = _constraint_link({"type": 201, "clues": [{"value": value, "edge": edge}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": cells, "k": value})
        in puzzle.constraints
    )


def test_black_kropki_honors_a_labelled_non_two_value() -> None:
    # A black dot labelled with a ratio other than 2 is honored verbatim —
    # never silently treated as the default 2:1.
    payload = _constraint_link({"type": 201, "clues": [{"value": 3, "edge": 75}]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 3})
        in puzzle.constraints
    )


def test_multiple_black_kropki_clues_each_decode_to_their_own_constraint() -> None:
    payload = _constraint_link(
        {
            "type": 201,
            "clues": [{"value": 2, "edge": 75}, {"value": 2, "edge": 132}],
        }
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 2})
        in puzzle.constraints
    )
    assert (
        Constraint("pair-ratio", params={"cells": ["R8C6", "R8C7"], "k": 2})
        in puzzle.constraints
    )


def test_black_kropki_negative_list_warns_but_keeps_positive_clues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _constraint_link(
        {"type": 201, "clues": [{"value": 2, "edge": 75}], "negative": [1, 2]}
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("pair-ratio", params={"cells": ["R5C3", "R5C4"], "k": 2})
        in puzzle.constraints
    )
    assert "negative" in capsys.readouterr().err


def test_black_kropki_non_integer_value_raises_at_decode() -> None:
    # A non-integer wire value must never model a wrong verdict — refuse the
    # link instead.
    payload = _constraint_link({"type": 201, "clues": [{"value": 2.5, "edge": 75}]})

    with pytest.raises(ValueError, match="black-kropki value"):
        decode_link(payload)


# --- type 301 killer-cage decode ---------------


def test_cage_decodes_to_region_only_cage_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A no-sum cage (value 0) is honored silently as a plain region-only cage,
    # its raw indices mapped row-major to addresses ([18, 19] -> R3C1, R3C2).
    payload = _constraint_link(
        {"type": 301, "cages": [{"cells": [18, 19], "value": 0}]}
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("cage", params={"cells": ["R3C1", "R3C2"]}) in puzzle.constraints
    assert capsys.readouterr().err == ""


def test_cage_with_a_sum_decodes_to_a_cage_plus_a_group_sum(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A summed cage (value > 0) decodes to two constraints over the same
    # cells: a no-repeats `cage` and the total as a `group-sum` — the killer
    # cage's recomposition (spec #240). No warning, the sum is honored.
    payload = _constraint_link({"type": 301, "cages": [{"cells": [0, 1], "value": 7}]})

    puzzle, _ = decode_link(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 7})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_multiple_cages_each_decode_to_their_own_constraint() -> None:
    payload = _constraint_link(
        {
            "type": 301,
            "cages": [
                {"cells": [0, 1], "value": 0},
                {"cells": [18, 19], "value": 0},
            ],
        }
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert Constraint("cage", params={"cells": ["R3C1", "R3C2"]}) in puzzle.constraints


# --- type 2001 cosmetic-cage graduation (ADR-0008) ---------------


def test_cosmetic_cage_with_numeric_label_decodes_to_a_killer_cage_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A numeric string `value` is the only channel an out-of-range killer sum
    # (a doubler inside a cage) reaches gridfind through, so it graduates to a
    # `cage` plus the total as a `group-sum` over the same cells. Cells and
    # value nest under `cages`, the same wire shape as a `type 301` block.
    payload = _constraint_link(
        {"type": 2001, "cages": [{"value": "11", "cells": [0, 1, 2]}]}
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("cage", params={"cells": ["R1C1", "R1C2", "R1C3"]})
        in puzzle.constraints
    )
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2", "R1C3"], "sum": 11})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_cosmetic_cage_with_a_zero_label_decodes_to_a_bare_cage() -> None:
    # A `"0"` label carries no killer sum — a zero total is no total, the same
    # rule a sumless `type 301` and a non-numeric label both decode to: a
    # no-repeats `cage` with no `group-sum`.
    payload = _constraint_link(
        {"type": 2001, "cages": [{"value": "0", "cells": [0, 1]}]}
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert all(c.type != "group-sum" for c in puzzle.constraints)


@pytest.mark.parametrize(
    "label",
    ["Total", ""],
    ids=["non-numeric-label", "empty-label"],
)
def test_cosmetic_cage_without_a_numeric_label_decodes_to_a_bare_cage(
    label: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A label carrying no killer sum still leaves a rule: every non-disabled
    # cosmetic cage is a killer cage, so it emits a no-repeats `cage` with no
    # `group-sum`, exactly like a sumless `type 301`.
    payload = _constraint_link(
        {"type": 2001, "cages": [{"value": label, "cells": [0, 1]}]}
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert all(c.type != "group-sum" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_multiple_cosmetic_cages_each_decode_to_their_own_constraint() -> None:
    # One block carries many cages under `cages`, exactly as a `type 301`
    # block does — a real doubler export packs two cages into one block.
    payload = _constraint_link(
        {
            "type": 2001,
            "cages": [
                {"value": "7", "cells": [0, 1]},
                {"value": "11", "cells": [18, 19]},
            ],
        }
    )

    puzzle, _ = decode_link(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 7})
        in puzzle.constraints
    )
    assert Constraint("cage", params={"cells": ["R3C1", "R3C2"]}) in puzzle.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R3C1", "R3C2"], "sum": 11})
        in puzzle.constraints
    )


# --- type 300 thermo decode -----------------


def test_normal_thermo_decodes_to_ordered_path_constraint() -> None:
    # Raw indices map row-major to addresses, bulb first, order preserved —
    # [0, 1, 2] -> R1C1, R1C2, R1C3.
    payload = _constraint_link(
        {"type": 300, "slow": False, "thermometers": [[0, 1, 2]]}
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": False})
        in puzzle.constraints
    )


def test_multiple_thermo_paths_each_decode_to_their_own_constraint() -> None:
    payload = _constraint_link(
        {
            "type": 300,
            "slow": False,
            "thermometers": [[0, 1, 2], [9, 18, 27]],
        }
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": False})
        in puzzle.constraints
    )
    assert (
        Constraint("thermo", params={"path": ["R2C1", "R3C1", "R4C1"], "slow": False})
        in puzzle.constraints
    )


def test_slow_thermo_decodes_with_slow_true_on_the_constraint() -> None:
    payload = _constraint_link({"type": 300, "slow": True, "thermometers": [[0, 1, 2]]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": True})
        in puzzle.constraints
    )


def test_two_cell_thermo_decodes_the_bare_inequality_path() -> None:
    payload = _constraint_link({"type": 300, "slow": False, "thermometers": [[0, 1]]})

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2"], "slow": False})
        in puzzle.constraints
    )


def test_thermo_style_is_ignored() -> None:
    payload = _constraint_link(
        {
            "type": 300,
            "slow": False,
            "thermometers": [[0, 1, 2]],
            "style": {"color": "#ff0000", "thickness": 5},
        }
    )

    puzzle, _ = decode_link(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": False})
        in puzzle.constraints
    )


def test_disabled_thermo_block_decodes_to_nothing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _constraint_link(
        {"type": 300, "slow": False, "thermometers": [[0, 1, 2]], "disabled": True}
    )

    puzzle, _ = decode_link(payload)

    assert all(c.type != "thermo" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


# --- shared: a disabled or empty block of any decoded family is a no-op ---


@pytest.mark.parametrize(
    ("block", "decoded_types"),
    [
        pytest.param(
            {"type": 202, "clues": [{"value": 10, "edge": 70}], "disabled": True},
            ("x", "v", "group-sum"),
            id="xv-disabled",
        ),
        pytest.param(
            {"type": 202, "clues": [], "negative": []},
            ("x", "v", "group-sum"),
            id="xv-empty",
        ),
        pytest.param(
            {"type": 200, "clues": [{"value": 1, "edge": 75}], "disabled": True},
            ("pair-difference",),
            id="kropki-disabled",
        ),
        pytest.param(
            {"type": 200, "clues": [], "negative": []},
            ("pair-difference",),
            id="kropki-empty",
        ),
        pytest.param(
            {"type": 301, "cages": [{"cells": [0, 1], "value": 7}], "disabled": True},
            ("cage",),
            id="cage-disabled",
        ),
        pytest.param({"type": 301, "cages": []}, ("cage",), id="cage-empty"),
        pytest.param(
            {
                "type": 2001,
                "cages": [{"value": "7", "cells": [0, 1]}],
                "disabled": True,
            },
            ("cage",),
            id="cosmetic-cage-disabled",
        ),
        pytest.param({"type": 2001, "cages": []}, ("cage",), id="cosmetic-cage-empty"),
        pytest.param(
            {"type": 300, "slow": False, "thermometers": [[0, 1]], "disabled": True},
            ("thermo",),
            id="thermo-disabled",
        ),
        pytest.param(
            {"type": 300, "slow": False, "thermometers": []},
            ("thermo",),
            id="thermo-empty",
        ),
    ],
)
def test_disabled_or_empty_block_decodes_to_nothing_quietly(
    block: dict[str, object],
    decoded_types: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A disabled block (setter switched it off) and an empty one (no clues/cages)
    # both add no constraint and warn nothing — one rule across every decoded
    # family (XV, white-kropki, killer-cage).
    puzzle, _ = decode_link(_constraint_link(block))

    assert all(c.type not in decoded_types for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


# --- doubler decode (declared modifier cells) ---------------------------

# A 4x4 board's 2x2 boxes as a type-1 regions matrix, row-major.
_REGIONS_4X4 = [(i // 4 // 2) * 2 + (i % 4 // 2) for i in range(16)]
_DOUBLER_WIRE_CONSTRAINTS = [{"type": 0}, {"type": 1, "regions": _REGIONS_4X4}]


def _doubler_link(cells: list[dict[str, object]]) -> str:
    """A synthesised 4x4 doubler-flavored link: the standard 4x4 boxes and a
    caller-supplied cells array. A doubler cell is marked with the red bit,
    the same `colors` bit an S-cell uses."""
    return _encode(
        {"cells": cells, "size": 4, "constraints": _DOUBLER_WIRE_CONSTRAINTS}
    )


def test_doubler_link_reads_a_red_cell_into_a_declared_modifier() -> None:
    cells: list[dict[str, object]] = [{} for _ in range(16)]
    cells[0] = {"colors": _RED_BIT}
    payload = _doubler_link(cells)

    puzzle, state = decode_link(payload, LinkVariant(doubler=True))

    assert Constraint("doubler") in puzzle.constraints
    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives


def test_doubler_red_bit_is_orthogonal_to_the_digit_a_doubler_holds() -> None:
    # A doubler holds one digit worth twice its value — unlike an S-cell, a red
    # cell may carry a given. The red bit adds the modifier mark; the given
    # still lands.
    cells: list[dict[str, object]] = [{} for _ in range(16)]
    cells[5] = {"colors": _RED_BIT, "given": True, "value": 3}
    payload = _doubler_link(cells)

    puzzle, state = decode_link(payload, LinkVariant(doubler=True))

    assert Given("R2C2", 3) in puzzle.givens
    assert ModifierDirective("R2C2", is_modifier=True) in state.modifier_directives


def test_without_the_doubler_flag_the_red_mark_is_ignored() -> None:
    cells: list[dict[str, object]] = [{} for _ in range(16)]
    cells[0] = {"colors": _RED_BIT}
    payload = _doubler_link(cells)

    puzzle, state = decode_link(payload)

    assert Constraint("doubler") not in puzzle.constraints
    assert state.modifier_directives == ()


def test_a_link_declaring_both_schrodinger_and_doubler_is_refused() -> None:
    # The two variants share the red bit, so a single link is one or the other.
    payload = _doubler_link([{} for _ in range(16)])

    with pytest.raises(ValueError, match="both"):
        decode_link(payload, LinkVariant(schrodinger=True, doubler=True))


def test_link_variant_refuses_schrodinger_and_doubler_together() -> None:
    # The invariant lives on the value: the two variants share the red bit, so
    # a link is one or the other — refused at construction, before any decode.
    with pytest.raises(ValueError, match="both"):
        LinkVariant(schrodinger=True, doubler=True)


def test_link_variant_refuses_a_non_classic_reading_under_schrodinger() -> None:
    with pytest.raises(ValueError, match="reading"):
        LinkVariant(schrodinger=True, reading="sum-valued")


def test_link_variant_leaves_a_stray_reading_alone_without_schrodinger() -> None:
    # reading is only meaningful under --schrodinger; a value carried without it
    # is ignored, never validated, matching the decoder's own leniency.
    assert LinkVariant(reading="sum-valued").reading == "sum-valued"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["link"], LinkVariant()),
        (["--schrodinger", "link"], LinkVariant(schrodinger=True)),
        (["--doubler", "link"], LinkVariant(doubler=True)),
        (
            ["--schrodinger", "--reading", "classic", "link"],
            LinkVariant(schrodinger=True, reading="classic"),
        ),
    ],
    ids=["bare", "schrodinger", "doubler", "reading"],
)
def test_link_variant_from_argv_reads_the_flags(
    argv: list[str], expected: LinkVariant
) -> None:
    # from_argv is the one parser the case-file scripts share, so the oracle and
    # the eval view never diverge from a hand-copied flag read.
    assert LinkVariant.from_argv(argv) == expected


_PLAIN = LinkVariant()


@pytest.mark.parametrize(
    ("cell", "variant", "domain", "expected"),
    [
        (
            {"given": True, "value": 5},
            _PLAIN,
            range(1, 10),
            _CellDecode(givens=(Given("R1C1", 5),)),
        ),
        (
            {"value": 5},
            _PLAIN,
            range(1, 10),
            _CellDecode(places=(Placement("R1C1", 5),)),
        ),
        (
            {"candidates": (1 << 2) | (1 << 5)},
            _PLAIN,
            range(1, 10),
            _CellDecode(candidates=(Candidate("R1C1", frozenset({2, 5})),)),
        ),
        ({}, _PLAIN, range(1, 10), _CellDecode()),
        (
            {"colors": _RED_BIT, "given": True, "value": 3},
            LinkVariant(doubler=True),
            range(1, 10),
            _CellDecode(
                givens=(Given("R1C1", 3),),
                modifier_directives=(ModifierDirective("R1C1", is_modifier=True),),
            ),
        ),
        (
            {"colors": _RED_BIT, "candidates": (1 << 2) | (1 << 7)},
            LinkVariant(schrodinger=True),
            range(1, 11),
            _CellDecode(s_directives=(SCellPin("R1C1", frozenset({2, 7})),)),
        ),
    ],
    ids=["given", "placement", "candidate", "empty", "doubler", "schrodinger-pin"],
)
def test_decode_cell_returns_one_cells_directives(
    cell: dict[str, object],
    variant: LinkVariant,
    domain: range,
    expected: _CellDecode,
) -> None:
    # _decode_cell is the one home for per-cell decode: it returns the directives
    # a single cell yields as one value, and the same function serves all three
    # variants.
    assert _decode_cell(cell, "R1C1", variant, domain) == expected
