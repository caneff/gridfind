"""`thermo` behaviour, tested at two seams.

Mirrors `pair_difference_test.py`: the direct rule readback —
that a clue emitted its own edges (strict for normal, non-strict for slow),
not that a solve happened to satisfy them — plus verdict-seam behaviour
(found/broke).
"""

import pytest

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.conftest import thermo_rules
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _thermo(path: tuple[str, ...]) -> Constraint:
    return Constraint("thermo", params={"path": list(path), "slow": False})


def _slow_thermo(path: tuple[str, ...]) -> Constraint:
    return Constraint("thermo", params={"path": list(path), "slow": True})


@pytest.mark.parametrize(
    ("constraints", "expected"),
    [
        (
            (_thermo(("R1C1", "R1C2", "R1C3")),),
            [[("R1C1", "R1C2"), ("R1C2", "R1C3")]],
        ),
        (
            (_thermo(("R1C1", "R1C2")),),
            [[("R1C1", "R1C2")]],
        ),
        (
            (
                _thermo(("R1C1", "R1C2", "R1C3")),
                _thermo(("R3C3", "R3C4")),
            ),
            [[("R1C1", "R1C2"), ("R1C2", "R1C3")], [("R3C3", "R3C4")]],
        ),
        (
            (_slow_thermo(("R1C1", "R1C2", "R1C3")),),
            [[("R1C1", "R1C2"), ("R1C2", "R1C3")]],
        ),
        (
            (
                _thermo(("R1C1", "R1C2", "R1C3")),
                _slow_thermo(("R3C3", "R3C4")),
            ),
            [[("R1C1", "R1C2"), ("R1C2", "R1C3")], [("R3C3", "R3C4")]],
        ),
    ],
    ids=[
        "three-cell path",
        "two-cell path is one edge",
        "two clues",
        "slow path",
        "normal clue and slow clue together",
    ],
)
def test_thermo_emits_one_edge_per_consecutive_pair(
    constraints: tuple[Constraint, ...],
    expected: list[list[tuple[str, str]]],
) -> None:
    puzzle = Puzzle(board=BOARD, constraints=constraints)
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)

    assert thermo_rules(engine) == expected


def test_a_satisfiable_normal_thermo_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_thermo(("R1C1", "R1C2", "R1C3")),),
        givens=(Given(address="R1C1", digit=1),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, b, c = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert a < b < c


def test_an_impossible_thermo_resolves_broke() -> None:
    # Both cells pinned equal — a strict a < b cannot hold.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_thermo(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_thermo_longer_than_the_grid_can_strictly_climb_resolves_broke() -> None:
    # A 9x9 board's values top out at 9 — a strictly increasing 10-cell path
    # has no completion.
    path = (*(f"R1C{c}" for c in range(1, 10)), "R2C1")
    puzzle = Puzzle(board=BOARD, constraints=(_thermo(path),))

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_two_clues_each_constrain_their_own_path_independently() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(
            _thermo(("R1C1", "R1C2", "R1C3")),
            _thermo(("R3C3", "R3C4")),
        ),
        givens=(Given(address="R1C1", digit=1), Given(address="R3C3", digit=2)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, b, c = (result.witness[address][0] for address in ("R1C1", "R1C2", "R1C3"))
    assert a < b < c
    d, e = (result.witness[address][0] for address in ("R3C3", "R3C4"))
    assert d < e


def test_a_slow_thermo_with_equal_neighbors_resolves_found() -> None:
    # Both cells pinned equal — a normal thermo would break here, but a slow
    # thermo's non-strict <= allows the repeat.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_slow_thermo(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=5)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    a, b = (result.witness[address][0] for address in ("R1C1", "R1C2"))
    assert a == b == 5


def test_a_slow_thermo_forced_to_descend_resolves_broke() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_slow_thermo(("R1C1", "R1C2")),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_slow_thermo_longer_than_the_grid_still_resolves_found() -> None:
    # Repeats are allowed, so a slow path has no length ceiling, unlike a
    # normal thermo — a 10-cell flat line on a 9x9 board is fine.
    path = (*(f"R1C{c}" for c in range(1, 10)), "R2C1")
    puzzle = Puzzle(board=BOARD, constraints=(_slow_thermo(path),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    values = [result.witness[address][0] for address in path]
    assert values == sorted(values)
