from hypothesis import given
from hypothesis import strategies as st

from gridfind.puzzle import (
    EMPTY,
    Board,
    Candidate,
    Given,
    Place,
    Puzzle,
    Variant,
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

VARIANTS = st.builds(
    Variant,
    type=st.text(min_size=1),
    params=st.dictionaries(PARAM_KEYS, PARAM_VALUES, max_size=4),
)
GIVENS = st.builds(Given, address=ADDRESSES, digit=DIGITS)
PLACES = st.builds(Place, address=ADDRESSES, digit=DIGITS)
CANDIDATES = st.builds(
    Candidate,
    address=ADDRESSES,
    digits=st.sets(DIGITS, min_size=1).map(frozenset),
)
PUZZLES = st.builds(
    Puzzle,
    board=st.builds(Board, size=st.integers(1, 25)),
    variants=st.lists(VARIANTS, max_size=4).map(tuple),
    givens=st.lists(GIVENS, max_size=4).map(tuple),
)
WORKING_STATES = st.builds(
    WorkingState,
    places=st.lists(PLACES, max_size=4).map(tuple),
    candidates=st.lists(CANDIDATES, max_size=4).map(tuple),
)


def test_puzzle_round_trips_through_json() -> None:
    puzzle = Puzzle(
        board=Board(size=9),
        variants=(Variant(type="rows-distinct"),),
        givens=(Given(address="R1C1", digit=5),),
    )

    assert Puzzle.from_json(puzzle.to_json()) == puzzle


def test_working_state_round_trips_through_json() -> None:
    state = WorkingState(
        places=(Place(address="R5C5", digit=7),),
        candidates=(Candidate(address="R6C6", digits=frozenset({5, 6, 7})),),
    )

    assert WorkingState.from_json(state.to_json()) == state


def test_empty_is_the_working_state_default() -> None:
    assert WorkingState() == EMPTY
    assert EMPTY.places == ()
    assert EMPTY.candidates == ()


def test_variant_with_arbitrary_params_round_trips() -> None:
    killer = Variant(type="killer", params={"cells": ["R1C1", "R1C2"], "sum": 5})
    puzzle = Puzzle(board=Board(size=9), variants=(killer,))

    restored = Puzzle.from_json(puzzle.to_json())

    assert restored == puzzle
    assert restored.variants[0].params == {"cells": ["R1C1", "R1C2"], "sum": 5}


@given(puzzle=PUZZLES)
def test_any_puzzle_round_trips_through_json(puzzle: Puzzle) -> None:
    assert Puzzle.from_json(puzzle.to_json()) == puzzle


@given(state=WORKING_STATES)
def test_any_working_state_round_trips_through_json(state: WorkingState) -> None:
    assert WorkingState.from_json(state.to_json()) == state
