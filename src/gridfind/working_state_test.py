from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import resolve
from gridfind.working_state import Candidate, Given, Place, apply, parse


def test_parse_reads_the_header_stack():
    ws = parse("stack: board\ngiven R1C1 5\n")
    assert ws.stack == ["board"]


def test_parse_reads_a_multi_layer_header():
    ws = parse("stack: board, rows-distinct\n")
    assert ws.stack == ["board", "rows-distinct"]


def test_parse_reads_given_place_and_candidate_directives():
    ws = parse("stack: board\ngiven R1C1 5\nplace R1C2 6\ncandidate R1C3 {1,2,3}\n")
    assert ws.directives == [
        Given(address="R1C1", digit=5),
        Place(address="R1C2", digit=6),
        Candidate(address="R1C3", digits=frozenset({1, 2, 3})),
    ]


def test_apply_given_pins_the_cell_to_one_value():
    (board,) = resolve(["board"])
    engine = build_engine([board])
    ws = parse("stack: board\ngiven R1C1 5\n")

    apply(engine, ws)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    (var,) = engine.cells["R1C1"].content
    assert solver.value(var) == 5


def test_apply_given_and_conflicting_place_is_infeasible():
    (board,) = resolve(["board"])
    engine = build_engine([board])
    ws = parse("stack: board\ngiven R1C1 5\nplace R1C1 6\n")

    apply(engine, ws)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)
    assert status == cp_model.INFEASIBLE


def test_apply_candidate_excluding_the_given_is_infeasible():
    (board,) = resolve(["board"])
    engine = build_engine([board])
    ws = parse("stack: board\ngiven R1C1 5\ncandidate R1C1 {1,2,3}\n")

    apply(engine, ws)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)
    assert status == cp_model.INFEASIBLE
