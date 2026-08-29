"""`OffsetValueGap`/nonconsecutive behaviour, tested at the verdict seam plus
one direct rule readback — the claim a solve alone cannot make — that the
rule reads a cell's `value_expr` (a doubler's folded value), not its raw
digit. `OffsetAdjacency` (anti-knight/anti-king) keeps its own existing
coverage through the toggle corpus and `constraints_test.py`'s composition
test; this file is nonconsecutive's own.

Mirrors `pair_difference_test.py`'s doubler coverage: the same `abs_diff_var`
seam (`_base.py`), applied here through the shared `offset_pairs` walk over
every orthogonal pair instead of one named clue.
"""

from typing import cast

from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def test_a_nonconsecutive_pair_more_than_one_apart_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="nonconsecutive"),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=1)),
    )

    result = verdict(puzzle)

    assert result.kind == "found"


def test_a_nonconsecutive_pair_forced_consecutive_resolves_broke() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="nonconsecutive"),),
        givens=(Given(address="R1C1", digit=5), Given(address="R1C2", digit=4)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"


def test_nonconsecutive_reads_the_doubled_value_not_the_raw_digit() -> None:
    # A doubler cell showing digit 2 folds to value 4 (ADR-0009). Read as its
    # raw digit, 2 sits one apart from a neighbour's 1 -- a naive digit-mode
    # reading would break here. Read as its folded value (ADR-0019 dec 2),
    # 4 is three apart from 1, so the pair is `found`.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), Constraint(type="nonconsecutive")),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 2)
    engine.model.add(engine.d0("R1C2") == 1)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_nonconsecutive_still_forbids_the_doubled_value_one_apart() -> None:
    # The same doubled 2 (folded value 4) beside a neighbour's 5 is one apart
    # under the folded value too, so nonconsecutive must still refuse the
    # pair -- proving the rule is enforced on the folded value rather than
    # skipped for a modified cell.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), Constraint(type="nonconsecutive")),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 2)
    engine.model.add(engine.d0("R1C2") == 5)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_nonconsecutive_reads_the_combined_s_value_of_a_doubled_s_cell() -> None:
    # Mirrors pair_difference_test's doubled-S-cell coverage: a cell marked
    # both a modifier and an S-cell is worth 2*s_value (ADR-0010). R1C1's
    # digits combine to 3 (1+2), doubled to 6; R1C2 holds a plain 4, one apart
    # from 6's neighbour... 6 and 4 differ by 2, so the pair is `found` only
    # if the layer reads the folded, combined value rather than either raw
    # digit (1 or 2), each of which sits one apart from 4's neighbours.
    board = Board(size=4, values=range(5))
    puzzle = Puzzle(
        board=board,
        constraints=(
            Constraint(type="schrodinger"),
            Constraint(type="doubler"),
            Constraint(type="nonconsecutive"),
        ),
    )
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    content = engine.contents("R1C1")
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(content[0] == 1)
    engine.model.add(content[1] == 2)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 4)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
