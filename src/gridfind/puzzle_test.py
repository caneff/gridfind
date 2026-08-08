import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gridfind.puzzle import (
    Board,
    Candidate,
    Constraint,
    Given,
    Placement,
    Puzzle,
    WorkingState,
)

MIN_DIGIT = 0
MAX_DIGIT = 9

ADDRESSES = st.builds(lambda r, c: f"R{r}C{c}", st.integers(1, 9), st.integers(1, 9))
DIGITS = st.integers(MIN_DIGIT, MAX_DIGIT)

# JSON scalars/arrays that survive a json round-trip exactly (no float — repr
# round-trips but NaN/inf don't, and exactness is the property under test).
JSON_SCALARS = st.none() | st.booleans() | st.integers() | st.text()
# "type" can't be a param key: the wire form spreads params flat beside `type`.
PARAM_KEYS = st.text(min_size=1).filter(lambda k: k != "type")
# Arbitrary JSON values, nested — a data-bearing variant's params can be a
# list-of-pairs (a thermo path) or a nested object, not just flat scalars.
PARAM_VALUES = st.recursive(
    JSON_SCALARS,
    lambda children: st.lists(children) | st.dictionaries(PARAM_KEYS, children),
    max_leaves=6,
)

# Any non-empty range a setter might hand a board — most differ from the
# size-derived default and so must survive the round-trip through a `values`
# key; the rest collapse onto the default and write no key at all.
BOARD_VALUES = st.builds(
    lambda start, span, step: range(start, start + span, step),
    st.integers(-5, 5),
    st.integers(1, 20),
    st.integers(1, 3),
)
# Either the values left out (derived from size) or chosen outright.
BOARDS = st.builds(Board, size=st.integers(1, 25)) | st.builds(
    Board, size=st.integers(1, 25), values=BOARD_VALUES
)

CONSTRAINTS = st.builds(
    Constraint,
    type=st.text(min_size=1),
    params=st.dictionaries(PARAM_KEYS, PARAM_VALUES, max_size=4),
)
GIVENS = st.builds(Given, address=ADDRESSES, digit=DIGITS)
PLACES = st.builds(Placement, address=ADDRESSES, digit=DIGITS)
CANDIDATES = st.builds(
    Candidate,
    address=ADDRESSES,
    digits=st.sets(DIGITS, min_size=1).map(frozenset),
)
PUZZLES = st.builds(
    Puzzle,
    board=BOARDS,
    constraints=st.lists(CONSTRAINTS, max_size=4).map(tuple),
    givens=st.lists(GIVENS, max_size=4).map(tuple),
)
WORKING_STATES = st.builds(
    WorkingState,
    places=st.lists(PLACES, max_size=4).map(tuple),
    candidates=st.lists(CANDIDATES, max_size=4).map(tuple),
)


def test_board_derives_its_values_from_size() -> None:
    assert Board(size=9).values == range(1, 10)
    assert Board(size=4).values == range(1, 5)


def test_board_keeps_the_values_a_caller_hands_it() -> None:
    assert Board(size=9, values=range(9)).values == range(9)


def test_board_refuses_an_empty_range_of_values() -> None:
    with pytest.raises(ValueError, match="non-empty range"):
        Board(size=9, values=range(5, 5))


def test_from_json_refuses_a_board_whose_serialized_values_are_empty() -> None:
    with pytest.raises(ValueError, match="non-empty range"):
        Puzzle.from_json(
            json.dumps(
                {
                    "board": {"size": 9, "values": [5, 5, 1]},
                    "constraints": [],
                    "givens": [],
                }
            )
        )


def test_a_board_with_non_default_values_round_trips_through_json() -> None:
    puzzle = Puzzle(board=Board(size=9, values=range(9)))

    assert Puzzle.from_json(puzzle.to_json()).board.values == range(9)
    assert Puzzle.from_json(puzzle.to_json()) == puzzle


def test_a_board_with_derived_values_serializes_without_a_values_key() -> None:
    puzzle = Puzzle(board=Board(size=6))

    assert json.loads(puzzle.to_json())["board"] == {"size": 6}


def test_puzzle_round_trips_through_json() -> None:
    # The worked example for `test_any_puzzle_round_trips_through_json` below:
    # the property covers this case, this states it in a form a reader can read.
    puzzle = Puzzle(
        board=Board(size=9),
        constraints=(Constraint(type="rows-distinct"),),
        givens=(Given(address="R1C1", digit=5),),
    )

    assert Puzzle.from_json(puzzle.to_json()) == puzzle


def test_puzzle_serializes_its_constraints_under_the_constraints_key() -> None:
    puzzle = Puzzle(board=Board(size=9), constraints=(Constraint(type="sudoku"),))

    assert json.loads(puzzle.to_json())["constraints"] == [{"type": "sudoku"}]


def test_working_state_round_trips_through_json() -> None:
    state = WorkingState(
        places=(Placement(address="R5C5", digit=7),),
        candidates=(Candidate(address="R6C6", digits=frozenset({5, 6, 7})),),
    )

    assert WorkingState.from_json(state.to_json()) == state


def test_constraint_with_arbitrary_params_round_trips() -> None:
    killer = Constraint(type="killer", params={"cells": ["R1C1", "R1C2"], "sum": 5})
    puzzle = Puzzle(board=Board(size=9), constraints=(killer,))

    restored = Puzzle.from_json(puzzle.to_json())

    assert restored == puzzle
    assert restored.constraints[0].params == {"cells": ["R1C1", "R1C2"], "sum": 5}


@given(puzzle=PUZZLES)
def test_any_puzzle_round_trips_through_json(puzzle: Puzzle) -> None:
    assert Puzzle.from_json(puzzle.to_json()) == puzzle


@given(state=WORKING_STATES)
def test_any_working_state_round_trips_through_json(state: WorkingState) -> None:
    assert WorkingState.from_json(state.to_json()) == state
