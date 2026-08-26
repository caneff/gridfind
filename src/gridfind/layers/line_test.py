"""`line` behaviour, tested at two seams, mirroring `thermo_test.py`: the
direct rule readback via `line_rules` (whisper) / `all_different_groups`
(renban) — that a clue emitted its own rule shape, not that a solve happened
to satisfy it — plus verdict-seam behaviour (found/broke) for every relation
the family carries so far. Palindrome, grouped-line, between, and lockout,
like clone (`clone_test.py`), have no structural readback helper of their
own — their rules read digit equality/group-membership/interval bounds, not
addresses, so their coverage stays at the verdict/direct-model seam.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import GridfindError, MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.conftest import all_different_groups, line_rules
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _mask(*digits: int) -> int:
    mask = 0
    for digit in digits:
        mask |= 1 << digit
    return mask


ENTROPIC_GROUPS = [_mask(1, 2, 3), _mask(4, 5, 6), _mask(7, 8, 9)]


def _whisper(path: tuple[str, ...], min_difference: int) -> Constraint:
    return Constraint(
        "line",
        params={
            "relation": "whisper",
            "path": list(path),
            "minDifference": min_difference,
        },
    )


def _renban(path: tuple[str, ...]) -> Constraint:
    return Constraint("line", params={"relation": "renban", "path": list(path)})


def _palindrome(path: tuple[str, ...]) -> Constraint:
    return Constraint("line", params={"relation": "palindrome", "path": list(path)})


def _between(path: tuple[str, ...]) -> Constraint:
    return Constraint("line", params={"relation": "between", "path": list(path)})


def _lockout(path: tuple[str, ...]) -> Constraint:
    return Constraint("line", params={"relation": "lockout", "path": list(path)})


def _double_arrow(path: tuple[str, ...]) -> Constraint:
    return Constraint("line", params={"relation": "double-arrow", "path": list(path)})


def _grouped(path: tuple[str, ...], groups: list[int]) -> Constraint:
    return Constraint(
        "line", params={"relation": "grouped", "path": list(path), "groups": groups}
    )


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        (
            (_whisper(("R1C1", "R1C2", "R1C3"), 5),),
            [[("R1C1", "R1C2", 5), ("R1C2", "R1C3", 5)]],
        ),
        (
            (_whisper(("R1C1", "R1C2"), 4),),
            [[("R1C1", "R1C2", 4)]],
        ),
        (
            (
                _whisper(("R1C1", "R1C2", "R1C3"), 5),
                _whisper(("R3C3", "R3C4"), 4),
            ),
            [[("R1C1", "R1C2", 5), ("R1C2", "R1C3", 5)], [("R3C3", "R3C4", 4)]],
        ),
    ],
    ids=["three-cell path", "two-cell path is one edge", "two clues"],
)
def test_whisper_emits_one_edge_per_consecutive_pair(
    constraints: tuple[Constraint, ...],
    expected: list[list[tuple[str, str, int]]],
) -> None:
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert line_rules(engine) == expected


def test_a_satisfiable_whisper_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_whisper(("R1C1", "R1C2"), 5),),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, b = (result.witness[address][0] for address in ("R1C1", "R1C2"))
    assert abs(a - b) >= 5


def test_an_impossible_whisper_resolves_broke() -> None:
    # Both cells pinned equal — a gap of 0 cannot meet a minimum of 5.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_whisper(("R1C1", "R1C2"), 5),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_clues_each_constrain_their_own_path_independently() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _whisper(("R1C1", "R1C2", "R1C3"), 5),
            _whisper(("R3C3", "R3C4"), 4),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, b, c = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert abs(a - b) >= 5
    assert abs(b - c) >= 5
    d, e = (result.witness[address][0] for address in ("R3C3", "R3C4"))
    assert abs(d - e) >= 4


def test_a_whisper_with_no_min_difference_raises() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(
                "line", params={"relation": "whisper", "path": ["R1C1", "R1C2"]}
            ),
        ),
    )

    with pytest.raises(KeyError):
        verdict(puzzle)


def test_an_unrecognized_line_relation_raises() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(
                "line",
                params={"relation": "not-a-real-relation", "path": ["R1C1", "R1C2"]},
            ),
        ),
    )

    with pytest.raises(KeyError):
        verdict(puzzle)


def test_whisper_reads_the_doubled_value_when_a_cell_is_the_modifier() -> None:
    # A gap of >= 5 needs the tip doubled above 9 — unreachable as a raw
    # digit (max 9) but reachable once R1C1 doubles: 2*5 = 10, a gap of 9
    # against R1C2's 1. Forcing R1C1 to be the modifier isolates the claim —
    # the edge only balances if whisper read R1C1's folded value, not its
    # raw digit.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _whisper(("R1C1", "R1C2"), 5)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 5)
    engine.model.add(engine.d0("R1C2") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert (
        abs(2 * solver.value(engine.d0("R1C1")) - solver.value(engine.d0("R1C2"))) >= 5
    )


def test_whisper_reads_the_combined_s_value_of_a_doubled_s_cell() -> None:
    # R1C1's digits combine to 2 (0+2), doubled to 4 (ADR-0010); R1C2 is a
    # plain 0. A raw-digit reading could not clear a minimum gap of 4 off a
    # doubler-blind R1C1, so this only holds if whisper read R1C1's folded
    # value.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
            _whisper(("R1C2", "R1C1"), 4),
        ),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    content = engine.contents("R1C1")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 0)
    engine.model.add(content[1] == 2)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 0)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.value_expr("R1C1")) == 4


def test_a_satisfiable_renban_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_renban(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=5),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    values = sorted(result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert len(set(values)) == 3
    assert values[-1] - values[0] == 2


def test_a_renban_with_a_gap_resolves_broke() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_renban(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_renban_repeat_resolves_broke_with_no_region_backing() -> None:
    # No rows/cols/regions constraint at all — renban enforces its own
    # distinctness, so a repeat is broke even off any box or region.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_renban(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=3), Given(address="R1C2", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_renban_all_different_reaches_both_slots_of_a_widened_cell() -> None:
    # The set-structured Schrödinger split, read back structurally
    # (mirroring `cage_test.py`'s own widened-cell readback): renban's
    # all-different rule runs over both of a widened cell's slots, not just
    # its `d0`, so an S-cell contributes both digits to the run.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(Constraint(type="schrodinger"), _renban(("R1C1", "R1C2"))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)

    assert all_different_groups(engine) == [["R1C1", "R1C1", "R1C2", "R1C2"]]


def test_renban_schrodinger_cell_contributes_both_digits_to_the_run() -> None:
    # R1C1 is forced S with digits {0, 2}; R1C2 is a plain 1 — together the
    # 2-cell path seats the 3-digit run 0-1-2, feasible only because the
    # S-cell's second digit joins the run alongside its first.
    board = Board(size=2, values=range(3))
    puzzle = Puzzle(
        board=board,
        constraints=(Constraint(type="schrodinger"), _renban(("R1C1", "R1C2"))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 0)
    engine.model.add(r1c1[1] == 2)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_renban_schrodinger_cell_leaving_a_gap_resolves_infeasible() -> None:
    # Same shape as above, but the S-cell's second digit (3) leaves a gap
    # against the singleton's 1 — {0, 1, 3} is not a consecutive run, so this
    # must fail even though every digit is distinct. Proves `max` reads the
    # S-cell's real digit under its guard rather than the sentinel that would
    # sit there were the cell not S.
    board = Board(size=2, values=range(4))
    puzzle = Puzzle(
        board=board,
        constraints=(Constraint(type="schrodinger"), _renban(("R1C1", "R1C2"))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 0)
    engine.model.add(r1c1[1] == 3)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_a_mirrored_palindrome_resolves_found() -> None:
    # R1C1 and R9C9 are the mirror pair; both given the same digit mirrors
    # cleanly regardless of the free middle cell.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_palindrome(("R1C1", "R5C5", "R9C9")),),
        givens=(Given(address="R1C1", digit=3), Given(address="R9C9", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, c = (result.witness[address][0] for address in ("R1C1", "R9C9"))
    assert a == c


def test_an_unmirrored_palindrome_resolves_broke() -> None:
    # Both mirror-pair cells given, different digits — a direct contradiction
    # since no completion can make them equal.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_palindrome(("R1C1", "R5C5", "R9C9")),),
        givens=(Given(address="R1C1", digit=3), Given(address="R9C9", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_an_odd_length_palindromes_middle_cell_is_free() -> None:
    # Same mirrored ends both times; only the middle given digit changes.
    # Both resolve found, so no palindrome rule pins the middle to one value.
    for middle_digit in (1, 2):
        puzzle = Puzzle(
            board=BOARD,
            constraints=(_palindrome(("R1C1", "R5C5", "R9C9")),),
            givens=(
                Given(address="R1C1", digit=3),
                Given(address="R9C9", digit=3),
                Given(address="R5C5", digit=middle_digit),
            ),
        )

        result = verdict(puzzle)

        assert result.kind == "found"


def test_a_multi_slot_schrodinger_cell_on_the_palindrome_raises() -> None:
    # Palindrome is position-structured, unlike renban's set-structured
    # pooling: a Schrödinger-widened path cell has no defined mirror-pair
    # rule, so it refuses loud (via `sole`, engine.py) rather than guess one.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            _palindrome(("R1C1", "R2C2", "R3C3")),
        ),
    )

    with pytest.raises(GridfindError):
        verdict(puzzle)


def test_a_satisfiable_entropic_grouped_line_resolves_found() -> None:
    # One digit per band (low/mid/high) across the line's sole 3-cell window.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_grouped(("R1C1", "R2C2", "R3C3"), ENTROPIC_GROUPS),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R2C2", digit=4),
            Given(address="R3C3", digit=7),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_a_repeated_band_in_one_window_resolves_broke() -> None:
    # R1C1 and R2C2 both land in the low band {1,2,3} — the window's own
    # rule (one cell per band) is violated directly by the givens, no
    # completion needed.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_grouped(("R1C1", "R2C2", "R3C3"), ENTROPIC_GROUPS),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R2C2", digit=2),
            Given(address="R3C3", digit=7),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_the_band_repeats_every_group_count_cells_along_a_longer_line() -> None:
    # A 4-cell path has two overlapping windows (0-2, 1-3); since each window
    # is its own full permutation of the three bands and windows 0 and 1
    # share cells 1 and 2, cell 3 is forced into cell 0's band. Same band,
    # different digit (1 and 2, both low) resolves found; a different band
    # (1 low, 4 mid) resolves broke, isolating the cross-window cycle as the
    # sole cause.
    path = ("R1C1", "R2C2", "R3C3", "R4C4")

    found = Puzzle(
        board=BOARD,
        constraints=(_grouped(path, ENTROPIC_GROUPS),),
        givens=(Given(address="R1C1", digit=1), Given(address="R4C4", digit=2)),
    )
    broke = Puzzle(
        board=BOARD,
        constraints=(_grouped(path, ENTROPIC_GROUPS),),
        givens=(Given(address="R1C1", digit=1), Given(address="R4C4", digit=4)),
    )

    assert verdict(found).kind == "found"
    result = verdict(broke)
    assert result.kind == "broke"
    assert result.witness is None


@pytest.mark.parametrize(
    "groups",
    [
        pytest.param([_mask(1, 2), _mask(3, 4)], id="gap"),
        pytest.param([_mask(1, 2, 3, 4), _mask(4, 5, 6, 7, 8, 9)], id="overlap"),
    ],
)
def test_groups_that_do_not_partition_the_board_raise(groups: list[int]) -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_grouped(("R1C1", "R2C2", "R3C3"), groups),),
    )

    with pytest.raises(MalformedPuzzleError):
        verdict(puzzle)


def test_a_satisfiable_between_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_between(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=2), Given(address="R1C3", digit=8)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, c, b = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert min(a, b) < c < max(a, b)


def test_an_interior_digit_not_between_the_bulbs_resolves_broke() -> None:
    # Interior given 9, outside the (2, 8) bulb range — a direct
    # contradiction since all three cells are given.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_between(("R1C1", "R1C2", "R1C3")),),
        givens=(
            Given(address="R1C1", digit=2),
            Given(address="R1C2", digit=9),
            Given(address="R1C3", digit=8),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_an_interior_digit_equal_to_a_bulb_resolves_broke() -> None:
    # Between is strict — an interior digit equal to either bulb does not
    # count as "between" it.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_between(("R1C1", "R1C2", "R1C3")),),
        givens=(
            Given(address="R1C1", digit=2),
            Given(address="R1C2", digit=8),
            Given(address="R1C3", digit=8),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_between_line_bounds_regardless_of_which_end_is_larger() -> None:
    # Same shape as the satisfiable case, ends reversed (b < a) — the
    # relation reads min/max of the pair, not "first, then second".
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_between(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=8), Given(address="R1C3", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, c, b = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert min(a, b) < c < max(a, b)


def test_a_two_cell_between_line_asserts_nothing() -> None:
    # No interior cell — the two bulbs only bound; they are not themselves
    # constrained beyond that. Equal ends, which would make any interior
    # unsatisfiable, still resolve found since there is no interior to bound.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_between(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_between_reads_the_doubled_value_of_a_bulb() -> None:
    # R1C1 is the modifier bulb, raw digit 5 doubles to 10; R1C3 is the
    # other, plain bulb at 1. Interior R1C2 pinned to 8 falls inside (1, 10)
    # but outside (1, 5) — feasible only if between read R1C1's folded value.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _between(("R1C1", "R1C2", "R1C3"))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 5)
    engine.model.add(engine.d0("R1C2") == 8)
    engine.model.add(engine.d0("R1C3") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_between_reads_the_combined_s_value_of_a_doubled_s_cell() -> None:
    # R1C1's digits combine to 2 (0+2), doubled to 4 (ADR-0010); R1C3 is the
    # other bulb, plain 0. Interior R1C2 pinned to 3 sits inside (0, 4), but
    # could not sit strictly between two equal bulbs both read raw at 0 —
    # feasible only if between read R1C1's folded value.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
            _between(("R1C1", "R1C2", "R1C3")),
        ),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    content = engine.contents("R1C1")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 0)
    engine.model.add(content[1] == 2)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 3)
    engine.model.add(is_s["R1C3"] == 0)
    engine.model.add(engine.d0("R1C3") == 0)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.value_expr("R1C1")) == 4


def test_a_satisfiable_lockout_resolves_found() -> None:
    # Bulbs 2 and 7 clear the 9x9 threshold ((9-1)//2 = 4); the interior is
    # left to the solver, satisfied by anything outside (2, 7).
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_lockout(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=2), Given(address="R1C3", digit=7)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, c, b = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert abs(a - b) >= 4
    assert c < min(a, b) or c > max(a, b)


def test_an_interior_digit_inside_the_bulb_range_resolves_broke() -> None:
    # Bulbs 2 and 7 clear the threshold, but the interior given 5 sits
    # inside (2, 7) — a direct contradiction since all three cells are given.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_lockout(("R1C1", "R1C2", "R1C3")),),
        givens=(
            Given(address="R1C1", digit=2),
            Given(address="R1C2", digit=5),
            Given(address="R1C3", digit=7),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_bulbs_too_close_together_resolve_broke() -> None:
    # Bulbs 4 and 5 (gap 1) fall short of the 9x9 threshold of 4, regardless
    # of what the free interior cell could hold.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_lockout(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=4), Given(address="R1C3", digit=5)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_lockout_line_bounds_regardless_of_which_end_is_larger() -> None:
    # Same shape as the satisfiable case, ends reversed (b < a) — the
    # relation reads min/max of the pair, not "first, then second".
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_lockout(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=7), Given(address="R1C3", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, c, b = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert abs(a - b) >= 4
    assert c < min(a, b) or c > max(a, b)


def test_a_two_cell_lockout_line_only_checks_the_threshold() -> None:
    # No interior cell to bound — but unlike between, the endpoint gap is
    # still enforced with only two cells.
    close = Puzzle(
        board=BOARD,
        constraints=(_lockout(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
    )

    assert verdict(close).kind == "broke"

    far = Puzzle(
        board=BOARD,
        constraints=(_lockout(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=1), Given(address="R1C2", digit=9)),
    )

    assert verdict(far).kind == "found"


@pytest.mark.parametrize(
    ("size", "threshold"),
    [(4, 1), (6, 2), (9, 4)],
    ids=["4x4", "6x6", "9x9"],
)
def test_the_threshold_is_derived_from_board_size_not_the_wire(
    size: int, threshold: int
) -> None:
    board = Board(size=size)
    too_close = Puzzle(
        board=board,
        constraints=(_lockout(("R1C1", "R1C2")),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=threshold),
        ),
    )

    assert verdict(too_close).kind == "broke"

    wide_enough = Puzzle(
        board=board,
        constraints=(_lockout(("R1C1", "R1C2")),),
        givens=(
            Given(address="R1C1", digit=1),
            Given(address="R1C2", digit=threshold + 1),
        ),
    )

    assert verdict(wide_enough).kind == "found"


def test_lockout_reads_the_doubled_value_of_a_bulb() -> None:
    # R1C1 is the modifier bulb, raw digit 3 doubles to 6; R1C2 is the
    # other, plain bulb at 1. The raw gap (2) falls short of the 9x9
    # threshold (4); only the folded gap (5) clears it — feasible only if
    # lockout read R1C1's folded value.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _lockout(("R1C1", "R1C2"))),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 3)
    engine.model.add(engine.d0("R1C2") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert (
        abs(2 * solver.value(engine.d0("R1C1")) - solver.value(engine.d0("R1C2"))) >= 4
    )


def test_lockout_reads_the_combined_s_value_of_a_doubled_s_cell() -> None:
    # R1C1's digits combine to 2 (0+2), doubled to 4 (ADR-0010); R1C2 is a
    # plain 0. The raw digit (0) ties R1C2 (gap 0, short of the 4x4
    # threshold of 1); only the folded s_value (4) clears it — feasible only
    # if lockout read R1C1's folded value.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
            _lockout(("R1C2", "R1C1")),
        ),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    content = engine.contents("R1C1")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 0)
    engine.model.add(content[1] == 2)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 0)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.value_expr("R1C1")) == 4


def test_a_multi_slot_schrodinger_cell_on_the_grouped_line_raises() -> None:
    # Grouped-line is window-structured, the same posture as palindrome: a
    # Schrödinger-widened path cell has no defined single-window fold, so it
    # refuses loud (via `sole`, engine.py) rather than guess one.
    board = Board(size=4, values=range(5))
    groups = [_mask(0, 1), _mask(2, 3, 4)]
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            _grouped(("R1C1", "R2C2", "R3C3"), groups),
        ),
    )

    with pytest.raises(GridfindError):
        verdict(puzzle)


def test_a_satisfiable_double_arrow_resolves_found() -> None:
    # Bulbs 2 and 3 sum to 5; the interior is left to the solver, satisfied
    # only by 5.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_double_arrow(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=2), Given(address="R1C3", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, c, b = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert c == a + b


def test_an_interior_sum_unequal_to_the_bulb_sum_resolves_broke() -> None:
    # Interior given 6, unequal to the (2, 3) bulb sum of 5 — a direct
    # contradiction since all three cells are given.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_double_arrow(("R1C1", "R1C2", "R1C3")),),
        givens=(
            Given(address="R1C1", digit=2),
            Given(address="R1C2", digit=6),
            Given(address="R1C3", digit=3),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_double_arrow_sums_every_interior_cell() -> None:
    # A four-cell path: the two interior cells (R1C2, R1C3) must together sum
    # to the bulb sum (2 + 6 = 8), not just one of them — pinning both
    # interior cells' digits and leaving no freedom proves the sum runs over
    # the whole interior.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_double_arrow(("R1C1", "R1C2", "R1C3", "R1C4")),),
        givens=(
            Given(address="R1C1", digit=2),
            Given(address="R1C2", digit=3),
            Given(address="R1C3", digit=5),
            Given(address="R1C4", digit=6),
        ),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_a_double_arrow_line_is_reversal_invariant() -> None:
    # Same shape as the satisfiable case, ends reversed — swapping the bulbs
    # leaves both sides of the sum equality unchanged.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_double_arrow(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=3), Given(address="R1C3", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, c, b = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert c == a + b


def test_a_two_cell_double_arrow_line_always_resolves_broke() -> None:
    # No interior cell — the empty interior sums to 0, which can never equal
    # two positive bulb values, whatever the rest of the board holds.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_double_arrow(("R1C1", "R1C2")),),
    )

    assert verdict(puzzle).kind == "broke"


def test_double_arrow_reads_the_doubled_value_of_a_bulb() -> None:
    # R1C1 is the modifier bulb, raw digit 3 doubles to 6; R1C3 is the other,
    # plain bulb at 2. The interior R1C2 pinned to 8 equals the folded sum
    # (6 + 2) but not the raw sum (3 + 2) — feasible only if double-arrow read
    # R1C1's folded value.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            Constraint(type="doubler"),
            _double_arrow(("R1C1", "R1C2", "R1C3")),
        ),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 3)
    engine.model.add(engine.d0("R1C2") == 8)
    engine.model.add(engine.d0("R1C3") == 2)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_double_arrow_reads_the_combined_s_value_of_a_doubled_s_cell() -> None:
    # R1C1's digits combine to 1 (0+1), doubled to 2 (ADR-0010); R1C3 is a
    # plain bulb at 1. Interior R1C2 pinned to 3 equals the folded sum
    # (2 + 1) but not the raw sum (0 + 1) — feasible only if double-arrow read
    # R1C1's folded value.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
            _double_arrow(("R1C1", "R1C2", "R1C3")),
        ),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    content = engine.contents("R1C1")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 0)
    engine.model.add(content[1] == 1)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 3)
    engine.model.add(is_s["R1C3"] == 0)
    engine.model.add(engine.d0("R1C3") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(engine.value_expr("R1C1")) == 2
