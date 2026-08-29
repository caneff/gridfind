"""`numbered-rooms` behaviour, tested at two seams.

Mirrors `indexing_test.py`: the direct rule readback — that a clue emitted
its own `add_element` involution over the right line and target, not that a
solve happened to satisfy it — plus verdict-seam found/broke behaviour, and
the ADR-0009 digit-read exception (a doubler never shifts the index).

The width-1 tests above exercise a bare stack (no widening layer), where
`NumberedRooms` takes its `add_element` fast path. The S-cell tests below
stack `schrodinger` alongside `numbered-rooms` and drive the `verdict()`
seam directly (`SCellPin`/`SingletonPin` s_directives over `S_BOARD`'s
`0..N` domain, mirroring `indexing_test.py`'s own S-cell fixtures) —
membership over a widened cell's two slots, the near cell indexing from
both of its digits, and the out-of-range-position refusal all only have a
defined meaning once a widening layer is in the stack. Each broke fixture
is paired with a strip-and-recheck twin that flips it to found once the
`numbered-rooms` constraint is removed, so the clue is the sole cause of
the break.

These fixtures stand in for the `links/` corpus pair every other clue's
S-cell coverage rides, because no SudokuMaker link can express the
combination today. `numbered-rooms` reaches gridfind only through the
escape-the-grid frame (`sudokumaker.frame`), and the frame peel forbids a
widened board twice over: it recognises a frame only when the digit domain
is exactly two short of the width, which pins the domain to the inner
board's own size — while `schrodinger` needs more digits than the board is
wide — and the inner document it hands back carries only givens and
regions, dropping the `type 2001` S-cell marker cage that is the sole
decode-time S-cell channel.
"""

from __future__ import annotations

from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import numbered_rooms_rules
from gridfind.layers.numbered_rooms import NumberedRooms
from gridfind.layers.outside_cells import OutsideCells
from gridfind.puzzle import Board, Constraint, Given, Puzzle, WorkingState
from gridfind.s_directives import SCellPin, SDirective, SingletonPin
from gridfind.verdict import verdict

BOARD = Board(size=4)

# A Schrödinger board small enough to solve fast: 5 digits (0-4) over a
# 4-cell line, the classic `0..N` domain (ADR-0014). 0 names no position,
# so this domain is what makes the out-of-range refusal reachable at all.
S_BOARD = Board(size=4, values=range(5))

# The line ordered from the clue inward: R1C2 (near) through R4C2 (far), with
# R0C2 the outside cell above column 2.
_LINE = ("R1C2", "R2C2", "R3C2", "R4C2")


def _numbered_rooms(cells: tuple[str, ...] = ("R0C2", *_LINE)) -> Constraint:
    """`cells[0]` the outside cell, `cells[1:]` its line ordered from the
    clue inward — the shape `frame.py`'s decode and this layer share."""
    return Constraint("numbered-rooms", params={"cells": list(cells)})


def test_numbered_rooms_emits_one_element_per_group() -> None:
    puzzle = Puzzle(board=BOARD, constraints=(_numbered_rooms(),))
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert numbered_rooms_rules(engine) == [("R0C2", "R1C2", list(_LINE))]


def test_no_numbered_rooms_constraint_emits_nothing() -> None:
    engine = build_engine([GridCells(), OutsideCells(), NumberedRooms()], board=BOARD)

    assert numbered_rooms_rules(engine) == []


def test_near_cell_names_its_own_position_resolves_found() -> None:
    # R1C2 = 1 (nearest the outside cell) names position 1 — itself. The
    # outside cell must then equal R1C2's own digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_numbered_rooms(),),
        givens=(
            Given(address="R1C2", digit=1),
            Given(address="R2C2", digit=3),
            Given(address="R3C2", digit=4),
            Given(address="R4C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R0C2"][0] == 1


def test_near_cell_names_a_farther_position_resolves_found() -> None:
    # R1C2 = 3 names position 3, R3C2 — given 4 — so the outside cell must
    # hold 4, not R1C2's own digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_numbered_rooms(),),
        givens=(
            Given(address="R1C2", digit=3),
            Given(address="R2C2", digit=1),
            Given(address="R3C2", digit=4),
            Given(address="R4C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R0C2"][0] == 4


def test_numbered_rooms_contradiction_resolves_broke() -> None:
    # R1C2 = 3 names position 3 (R3C2, given 4), but the outside cell is
    # given 2 — a mismatch the rule must refuse.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_numbered_rooms(),),
        givens=(
            Given(address="R0C2", digit=2),
            Given(address="R1C2", digit=3),
            Given(address="R2C2", digit=1),
            Given(address="R3C2", digit=4),
            Given(address="R4C2", digit=2),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_numbered_rooms_reads_the_raw_digit_under_a_discovered_doubler() -> None:
    # R1C2 doubled to 3 folds to modifier_value 6 -- out of the line's 1..4
    # index range, so an index read through the folded value would be
    # infeasible. NumberedRooms reads d0 (ADR-0009's digit-read exception):
    # position 3 selects R3C2, and the outside cell tracks R3C2's own digit,
    # never influenced by the doubler.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _numbered_rooms()),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C2"] == 1)
    engine.model.add(engine.d0("R1C2") == 3)
    engine.model.add(engine.d0("R3C2") == 4)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.d0("R0C2")) == 4


def _s_verdict(
    constraints: tuple[Constraint, ...],
    s_directives: tuple[SDirective, ...],
    givens: tuple[Given, ...] = (),
) -> str:
    """The `verdict()` kind for an S-cell fixture: `constraints` over
    `S_BOARD`, with `s_directives` pinning each widened cell's digits."""
    puzzle = Puzzle(board=S_BOARD, constraints=constraints, givens=givens)
    return verdict(puzzle, WorkingState(s_directives=s_directives)).kind


_SCHRODINGER = Constraint(type="schrodinger")

# R1C2, the near cell, widened to hold both 1 and 3: it names position 1
# (itself) from one digit and position 3 (R3C2) from the other.
_NEAR_HOLDS_1_AND_3 = (SCellPin(address="R1C2", pair=frozenset({1, 3})),)


def test_s_cell_near_cell_indexes_from_both_of_its_digits_resolves_found() -> None:
    # Position 1 asks the outside cell to share a digit with R1C2 itself
    # ({1, 3}); position 3 asks it to share one with R3C2, given 3. The
    # outside cell holding 3 satisfies both demands at once.
    kind = _s_verdict(
        (_SCHRODINGER, _numbered_rooms()),
        _NEAR_HOLDS_1_AND_3,
        (Given(address="R3C2", digit=3),),
    )

    assert kind == "found"


def test_s_cell_near_cells_second_digit_contradiction_resolves_broke() -> None:
    # The outside cell holds 1 alone, which position 1 accepts (R1C2 holds
    # 1). The near cell's *second* digit (3) names position 3 — R3C2, given
    # 4 — and 1 is not among R3C2's digits, so the break exists only because
    # the near cell indexes from both of the digits it holds. The outside
    # cell is pinned a singleton, not merely given: a given fixes `d0` alone,
    # leaving a widened cell free to hold a second digit that matches.
    kind = _s_verdict(
        (_SCHRODINGER, _numbered_rooms()),
        (*_NEAR_HOLDS_1_AND_3, SingletonPin(address="R0C2", digit=1)),
        (Given(address="R3C2", digit=4),),
    )

    assert kind == "broke"


def test_s_cell_near_cells_second_digit_contradiction_flips_found_when_stripped() -> (
    None
):
    # Strip-and-recheck, minus the outside cell's own pin: `outside-cells`
    # creates R0C2 only for a constraint that names it, so without
    # `numbered-rooms` there is no such cell to pin.
    kind = _s_verdict(
        (_SCHRODINGER,),
        _NEAR_HOLDS_1_AND_3,
        (Given(address="R3C2", digit=4),),
    )

    assert kind == "found"


# The outside cell R0C2 is itself widened — `outside-cells` registers before
# `schrodinger`, which widens every cell it finds — so it holds a digit set,
# and the match may come from either slot.
_OUTSIDE_HOLDS_1_AND_4 = (
    SingletonPin(address="R1C2", digit=2),
    SCellPin(address="R0C2", pair=frozenset({1, 4})),
)


def test_s_cell_outside_cell_matched_by_its_second_digit_resolves_found() -> None:
    # The near cell R1C2 holds 2 alone, naming position 2 — R2C2, given 4.
    # The outside cell's match comes from its second slot, not its first.
    kind = _s_verdict(
        (_SCHRODINGER, _numbered_rooms()),
        _OUTSIDE_HOLDS_1_AND_4,
        (Given(address="R2C2", digit=4),),
    )

    assert kind == "found"


_OUTSIDE_HOLDS_1_AND_3 = (
    SingletonPin(address="R1C2", digit=2),
    SCellPin(address="R0C2", pair=frozenset({1, 3})),
)


def test_s_cell_outside_cell_sharing_no_digit_resolves_broke() -> None:
    # The same shape with the match removed: the outside cell holds {1, 3},
    # neither of which R2C2 (given 4) holds, so the line cell at the named
    # position and the outside cell share no digit.
    kind = _s_verdict(
        (_SCHRODINGER, _numbered_rooms()),
        _OUTSIDE_HOLDS_1_AND_3,
        (Given(address="R2C2", digit=4),),
    )

    assert kind == "broke"


def test_s_cell_outside_cell_sharing_no_digit_flips_found_when_stripped() -> None:
    # Strip-and-recheck, minus the outside cell's own pin — R0C2 exists only
    # while the clue that names it does.
    kind = _s_verdict(
        (_SCHRODINGER,),
        (SingletonPin(address="R1C2", digit=2),),
        (Given(address="R2C2", digit=4),),
    )

    assert kind == "found"


_NEAR_HOLDS_0 = (SingletonPin(address="R1C2", digit=0),)


def test_s_cell_near_cell_holding_no_position_resolves_broke() -> None:
    # 0 names no position on a 4-cell line, so a near cell forced to 0 has no
    # digit to index from. The rule refuses it outright rather than let the
    # clue fall silently satisfied for want of a position to fire on.
    kind = _s_verdict((_SCHRODINGER, _numbered_rooms()), _NEAR_HOLDS_0)

    assert kind == "broke"


def test_s_cell_near_cell_holding_no_position_flips_found_when_stripped() -> None:
    kind = _s_verdict((_SCHRODINGER,), _NEAR_HOLDS_0)

    assert kind == "found"


# A widening layer needs more digits than the board is wide, and nothing
# fixes where the extra digit sits. This board puts it above the line rather
# than below: 5 digits (1-5) over a 4-cell line, so 5 names no position.
_HIGH_DIGIT_BOARD = Board(size=4, values=range(1, 6))
_NEAR_HOLDS_5 = (SingletonPin(address="R1C2", digit=5),)


def test_s_cell_near_cell_holding_a_digit_past_the_line_resolves_broke() -> None:
    puzzle = Puzzle(
        board=_HIGH_DIGIT_BOARD, constraints=(_SCHRODINGER, _numbered_rooms())
    )

    result = verdict(puzzle, WorkingState(s_directives=_NEAR_HOLDS_5))

    assert result.kind == "broke"


def test_s_cell_near_cell_holding_a_digit_past_the_line_flips_found_when_stripped() -> (
    None
):
    puzzle = Puzzle(board=_HIGH_DIGIT_BOARD, constraints=(_SCHRODINGER,))

    result = verdict(puzzle, WorkingState(s_directives=_NEAR_HOLDS_5))

    assert result.kind == "found"
