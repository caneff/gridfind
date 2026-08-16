"""rellik-cage behaviour, tested at the seams the issue names: `verdict`
(mirroring `cage_test.py`), the emit seam via solver FEASIBLE/INFEASIBLE
with pinned cells, and the value channel via `modifier_value`/`s_value`
pinning (spec #427, issue #515).

A rellik (anti-) cage forbids any non-empty group of its cells from summing
to a chosen forbidden total. This file proves this layer's own behaviour in
isolation, bare (no composed `cage`) — the same shape `group_sum_test.py`
and `cage_test.py` use for their own layers. The composition with `cage`
(the real rellik-cage a setter places) is proven at the `verdict` seam in
`verdict_test.py`, mirroring `_killer_cage`.

The size-band prune is this layer's one piece of nontrivial logic: it must
never drop a group that could reach the target (the correctness floor), so
the hypothesis test below builds a bare board (no distinctness composed)
and asserts, over random cell counts, value domains, and targets, that a
size the layer prunes truly cannot reach the target — the claim a solve,
not a structural read, can prove.
"""

from __future__ import annotations

from typing import cast

from hypothesis import given, settings
from hypothesis import strategies as st
from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.rellik_cage import RellikCage
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board, Constraint, Given, Puzzle
from gridfind.verdict import verdict

BOARD = Board(size=9)


def _rellik_cage(cells: tuple[str, ...], target: int) -> Constraint:
    return Constraint(type="rellik-cage", params={"cells": list(cells), "sum": target})


def test_no_rellik_cage_constraint_emits_nothing() -> None:
    bare = build_engine([GridCells()], board=BOARD)
    with_layer = build_engine([GridCells(), RellikCage()], board=BOARD)

    assert len(with_layer.model.proto.constraints) == len(bare.model.proto.constraints)


def test_a_satisfiable_rellik_cage_resolves_found_with_a_witness() -> None:
    # Two free cells on a 1-9 board: plenty of pairs avoid summing to 5.
    puzzle = Puzzle(board=BOARD, constraints=(_rellik_cage(("R1C1", "R1C2"), 5),))

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"][0] + result.witness["R1C2"][0] != 5


def test_a_pair_forced_to_the_forbidden_total_resolves_broke() -> None:
    # Both cells are given, so the only possible sum is the one the rellik
    # cage forbids.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_rellik_cage(("R1C1", "R1C2"), 5),),
        givens=(Given(address="R1C1", digit=2), Given(address="R1C2", digit=3)),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_singleton_cell_equal_to_the_target_resolves_broke() -> None:
    # A single-cell group: the "one-or-more digits" rule bars a lone digit
    # equal to the forbidden total too.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_rellik_cage(("R1C1",), 5),),
        givens=(Given(address="R1C1", digit=5),),
    )

    result = verdict(puzzle)

    assert result.kind == "broke"
    assert result.witness is None


def test_a_singleton_cell_off_the_target_resolves_found() -> None:
    puzzle = Puzzle(
        board=BOARD,
        constraints=(_rellik_cage(("R1C1",), 5),),
        givens=(Given(address="R1C1", digit=3),),
    )

    result = verdict(puzzle)

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"][0] == 3


def test_a_reachable_pair_pinned_to_the_target_is_infeasible() -> None:
    # The emit seam directly: pinning both cells so their sum equals the
    # forbidden total must make the model infeasible.
    engine = build_engine(
        [GridCells(), RellikCage()],
        (_rellik_cage(("R1C1", "R1C2"), 5),),
        board=BOARD,
    )
    engine.model.add(engine.d0("R1C1") == 2)
    engine.model.add(engine.d0("R1C2") == 3)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_a_reachable_pair_pinned_off_the_target_is_feasible() -> None:
    engine = build_engine(
        [GridCells(), RellikCage()],
        (_rellik_cage(("R1C1", "R1C2"), 5),),
        board=BOARD,
    )
    engine.model.add(engine.d0("R1C1") == 2)
    engine.model.add(engine.d0("R1C2") == 4)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


@given(
    count=st.integers(min_value=1, max_value=6),
    domain_high=st.integers(min_value=1, max_value=9),
    target=st.integers(-5, 60),
)
@settings(max_examples=75)
def test_the_band_prune_only_drops_sizes_that_cannot_reach_the_target(
    count: int, domain_high: int, target: int
) -> None:
    # A bare board of `count` cells, each free over 1..domain_high, no
    # composed distinctness. If the layer pruned this cage's own size
    # (count) — i.e. emitted nothing — the reachable range [count,
    # count*domain_high] must not contain the target; if it did, the layer
    # would have wrongly dropped a reachable group. The grid is fixed at
    # 9x9 (room for up to 6 cage cells) independent of the value domain.
    board = Board(size=9, values=range(1, domain_high + 1))
    cells = tuple(f"R1C{c}" for c in range(1, count + 1))
    puzzle = Puzzle(board=board, constraints=(_rellik_cage(cells, target),))
    canonical, layers = build_stack(puzzle.constraints, size=board.size)
    engine = build_engine(layers, tuple(canonical), board=board)

    pruned = len(engine.model.proto.constraints) == 0
    reachable = count <= target <= count * domain_high

    if pruned:
        assert not reachable


def test_rellik_cage_reads_the_doubled_value_not_the_raw_digit() -> None:
    # R1C1's raw digit is 3 but its modifier_value is 6 (doubled); pinning
    # R1C2 to 4 only collides with the forbidden total 10 if the rellik
    # cage read the folded value (6 + 4), not the bare digit (3 + 4).
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _rellik_cage(("R1C1", "R1C2"), 10)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 1)
    engine.model.add(engine.d0("R1C1") == 3)
    engine.model.add(engine.d0("R1C2") == 4)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE


def test_rellik_cage_permits_the_raw_digit_pair_when_only_the_value_collides() -> None:
    # Companion to the above: with no modifier discovered on R1C1, its value
    # stays its raw digit 3, so 3 + 4 = 7 never touches the forbidden 10 —
    # feasible, proving the ban tracks the value channel, not a
    # digit-blind collision.
    puzzle = Puzzle(
        board=BOARD,
        constraints=(Constraint(type="doubler"), _rellik_cage(("R1C1", "R1C2"), 10)),
    )
    canonical, layers = build_stack(puzzle.constraints, size=BOARD.size)
    engine = build_engine(layers, tuple(canonical), board=BOARD)
    is_modifier = cast("dict[str, cp_model.IntVar]", engine.structures["is_modifier"])
    engine.model.add(is_modifier["R1C1"] == 0)
    engine.model.add(is_modifier["R1C2"] == 0)
    engine.model.add(engine.d0("R1C1") == 3)
    engine.model.add(engine.d0("R1C2") == 4)

    status = cp_model.CpSolver().solve(engine.model)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def test_rellik_cage_over_a_widened_cell_reads_its_s_value() -> None:
    # R1C1 is forced S with digits {2, 3}: under the default `sum` combine
    # its value is 5. R1C2 is a singleton at 2. The forbidden total 7 is
    # only hit if the ban read R1C1's folded s_value (5 + 2 = 7), not its
    # raw d0 (2 + 2 = 4, off the target).
    engine = build_engine(
        [GridCells(), Schrodinger(), RellikCage()],
        (_rellik_cage(("R1C1", "R1C2"), 7),),
        board=Board(size=4, values=range(5)),
    )
    is_s = cast("dict[str, cp_model.IntVar]", engine.structures["is_s"])
    r1c1 = engine.contents("R1C1")
    engine.model.add(is_s["R1C1"] == 1)
    engine.model.add(r1c1[0] == 2)
    engine.model.add(r1c1[1] == 3)
    engine.model.add(is_s["R1C2"] == 0)
    engine.model.add(engine.d0("R1C2") == 2)

    status = cp_model.CpSolver().solve(engine.model)

    assert status == cp_model.INFEASIBLE
