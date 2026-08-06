import contextlib

import pytest
from hypothesis import given
from hypothesis import strategies as st
from ortools.sat.python import cp_model

from gridfind.engine import build_engine
from gridfind.layers import resolve
from gridfind.working_state import (
    MAX_DIGIT,
    MIN_DIGIT,
    Candidate,
    Given,
    Place,
    apply,
    parse,
)

ADDRESSES = st.builds(lambda r, c: f"R{r}C{c}", st.integers(1, 9), st.integers(1, 9))
VALID_DIGITS = st.integers(MIN_DIGIT, MAX_DIGIT)
OUT_OF_RANGE_DIGITS = st.integers().filter(lambda d: d < MIN_DIGIT or d > MAX_DIGIT)


def test_parse_reads_the_header_stack() -> None:
    ws = parse("stack: board\ngiven R1C1 5\n")
    assert ws.stack == ["board"]


def test_parse_reads_a_multi_layer_header() -> None:
    ws = parse("stack: board, rows-distinct\n")
    assert ws.stack == ["board", "rows-distinct"]


def test_parse_reads_given_place_and_candidate_directives() -> None:
    ws = parse("stack: board\ngiven R1C1 5\nplace R1C2 6\ncandidate R1C3 {1,2,3}\n")
    assert ws.directives == [
        Given(address="R1C1", digit=5),
        Place(address="R1C2", digit=6),
        Candidate(address="R1C3", digits=frozenset({1, 2, 3})),
    ]


def test_apply_given_pins_the_cell_to_one_value() -> None:
    (board,) = resolve(["board"])
    engine = build_engine([board])
    ws = parse("stack: board\ngiven R1C1 5\n")

    apply(engine, ws)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    (var,) = engine.cells["R1C1"].content
    assert solver.value(var) == 5


def test_apply_given_and_conflicting_place_is_infeasible() -> None:
    (board,) = resolve(["board"])
    engine = build_engine([board])
    ws = parse("stack: board\ngiven R1C1 5\nplace R1C1 6\n")

    apply(engine, ws)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)
    assert status == cp_model.INFEASIBLE


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("stack: board\ngiven R1C1\n", "given"),
        ("stack: board\nplace R1C1\n", "place"),
        ("stack: board\ncandidate R1C1\n", "candidate"),
        ("stack: board\ncandidate R1C1 {}\n", "empty"),
        ("stack: board\ncandidate R1C1 {1,2,1}\n", "duplicate"),
        ("stack: board\ngiven R1C1 10\n", "out of range"),
        ("stack: board\ncandidate R1C1 {1,10}\n", "out of range"),
        ("stack: board\ncandidate R1C1 1,2,3\n", "digit set"),
    ],
    ids=[
        "given-missing-digit",
        "place-missing-digit",
        "candidate-missing-set",
        "empty-candidate-set",
        "duplicate-in-candidate-set",
        "given-digit-out-of-range",
        "candidate-digit-out-of-range",
        "candidate-set-missing-braces",
    ],
)
def test_parse_rejects_malformed_input(text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse(text)


@given(address=ADDRESSES, digit=VALID_DIGITS)
def test_parse_given_round_trips_any_valid_address_and_digit(
    address: str, digit: int
) -> None:
    ws = parse(f"stack: board\ngiven {address} {digit}\n")
    assert ws.directives == [Given(address=address, digit=digit)]


@given(address=ADDRESSES, digit=VALID_DIGITS)
def test_parse_place_round_trips_any_valid_address_and_digit(
    address: str, digit: int
) -> None:
    ws = parse(f"stack: board\nplace {address} {digit}\n")
    assert ws.directives == [Place(address=address, digit=digit)]


@given(address=ADDRESSES, digits=st.sets(VALID_DIGITS, min_size=1, max_size=10))
def test_parse_candidate_round_trips_any_valid_digit_set(
    address: str, digits: set[int]
) -> None:
    literal = "{" + ",".join(str(d) for d in digits) + "}"
    ws = parse(f"stack: board\ncandidate {address} {literal}\n")
    assert ws.directives == [Candidate(address=address, digits=frozenset(digits))]


@given(digit=OUT_OF_RANGE_DIGITS)
def test_parse_given_rejects_any_out_of_range_digit(digit: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        parse(f"stack: board\ngiven R1C1 {digit}\n")


@given(
    digits=st.lists(VALID_DIGITS, min_size=2, max_size=10, unique=False).filter(
        lambda ds: len(ds) != len(set(ds))
    )
)
def test_parse_candidate_rejects_any_digit_set_with_a_duplicate(
    digits: list[int],
) -> None:
    literal = "{" + ",".join(str(d) for d in digits) + "}"
    with pytest.raises(ValueError, match="duplicate"):
        parse(f"stack: board\ncandidate R1C1 {literal}\n")


@given(text=st.text(max_size=200))
def test_parse_never_raises_anything_but_valueerror_on_arbitrary_text(
    text: str,
) -> None:
    with contextlib.suppress(ValueError):
        parse(text)


def test_apply_candidate_excluding_the_given_is_infeasible() -> None:
    (board,) = resolve(["board"])
    engine = build_engine([board])
    ws = parse("stack: board\ngiven R1C1 5\ncandidate R1C1 {1,2,3}\n")

    apply(engine, ws)

    solver = cp_model.CpSolver()
    status = solver.solve(engine.model)
    assert status == cp_model.INFEASIBLE
