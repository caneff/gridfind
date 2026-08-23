"""`line` behaviour, tested at two seams, mirroring `thermo_test.py`: the
direct rule readback via `line_rules` — that a clue emitted its own
adjacent-pair edges at the right threshold, not that a solve happened to
satisfy them — plus verdict-seam behaviour (found/broke) for the whisper
relation, the family's first row.
"""

from typing import cast

import pytest
from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.conftest import line_rules
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _whisper(path: tuple[str, ...], min_difference: int) -> Constraint:
    return Constraint(
        "line",
        params={
            "relation": "whisper",
            "path": list(path),
            "minDifference": min_difference,
        },
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
