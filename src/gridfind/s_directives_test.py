import pytest

from gridfind.engine import MalformedPuzzleError
from gridfind.s_directives import (
    BareSCell,
    BareSingleton,
    HalfSCell,
    SCellMarkRestriction,
    SCellPin,
    SDirective,
    SingletonPin,
    s_directive_from_dict,
    s_directive_to_dict,
    validate_s_cell_pair,
)

DIRECTIVE_CASES: list[tuple[SDirective, dict[str, object]]] = [
    (
        SingletonPin(address="R1C1", digit=4),
        {"kind": "singleton-pin", "address": "R1C1", "digit": 4},
    ),
    (
        SCellPin(address="R2C2", pair=frozenset({2, 7})),
        {"kind": "s-cell-pin", "address": "R2C2", "pair": [2, 7]},
    ),
    (
        BareSingleton(address="R3C3"),
        {"kind": "bare-singleton", "address": "R3C3"},
    ),
    (
        BareSCell(address="R4C4"),
        {"kind": "bare-s-cell", "address": "R4C4"},
    ),
    (
        HalfSCell(address="R5C5", digit=6),
        {"kind": "half-s-cell", "address": "R5C5", "digit": 6},
    ),
    (
        SCellMarkRestriction(address="R6C6", digits=frozenset({1, 4, 9})),
        {"kind": "s-cell-mark-restriction", "address": "R6C6", "digits": [1, 4, 9]},
    ),
]


@pytest.mark.parametrize(
    ("directive", "wire"),
    DIRECTIVE_CASES,
    ids=[d.kind for d, _ in DIRECTIVE_CASES],
)
def test_s_directive_to_dict_writes_the_kind_tagged_wire_shape(
    directive: SDirective, wire: dict[str, object]
) -> None:
    assert s_directive_to_dict(directive) == wire


@pytest.mark.parametrize(
    ("directive", "wire"),
    DIRECTIVE_CASES,
    ids=[d.kind for d, _ in DIRECTIVE_CASES],
)
def test_s_directive_from_dict_reads_the_kind_tagged_wire_shape(
    directive: SDirective, wire: dict[str, object]
) -> None:
    assert s_directive_from_dict(wire) == directive


def test_s_directive_from_dict_raises_key_error_for_an_unknown_kind() -> None:
    with pytest.raises(KeyError):
        s_directive_from_dict({"kind": "not-a-real-directive", "address": "R1C1"})


def test_s_directive_from_dict_raises_type_error_for_a_non_string_kind() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        s_directive_from_dict({"kind": 7, "address": "R1C1"})


@pytest.mark.parametrize(
    "pair",
    [
        pytest.param(frozenset([5, 5]), id="dedup-to-one"),
        pytest.param(frozenset({1, 2, 3}), id="size-three"),
    ],
)
def test_validate_s_cell_pair_refuses_a_pair_that_is_not_two_distinct_digits(
    pair: frozenset[int],
) -> None:
    with pytest.raises(MalformedPuzzleError, match="two distinct"):
        validate_s_cell_pair(pair)


def test_validate_s_cell_pair_accepts_two_distinct_digits() -> None:
    validate_s_cell_pair(frozenset({2, 7}))


@pytest.mark.parametrize(
    "pair",
    [
        pytest.param(frozenset([5, 5]), id="dedup-to-one"),
        pytest.param(frozenset({1, 2, 3}), id="size-three"),
    ],
)
def test_s_cell_pin_refuses_a_pair_that_is_not_two_distinct_digits(
    pair: frozenset[int],
) -> None:
    # The pair's shape is guarded at construction, so a malformed S-cell pin
    # can never exist in memory (ADR-0006 grill note). Counted after the
    # frozenset collapses duplicates: {5,5} is one digit, {1,2,3} is three.
    with pytest.raises(MalformedPuzzleError, match="two distinct"):
        SCellPin(address="R1C1", pair=pair)


def test_s_cell_pin_accepts_two_distinct_digits() -> None:
    assert SCellPin(address="R1C1", pair=frozenset({2, 7})).pair == frozenset({2, 7})
