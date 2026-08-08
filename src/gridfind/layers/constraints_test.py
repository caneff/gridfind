import pytest

from gridfind.layers import (
    LAYER_REGISTRY,
    UnknownLayerError,
    canonical_identity,
    expand_constraints,
    resolve_constraints,
)
from gridfind.puzzle import Constraint


def test_bare_constraints_resolve_to_the_matching_layer_instances() -> None:
    constraints = (Constraint(type="rows-distinct"), Constraint(type="cols-distinct"))

    assert resolve_constraints(constraints) == [
        LAYER_REGISTRY["rows-distinct"],
        LAYER_REGISTRY["cols-distinct"],
    ]


def test_sudoku_preset_expands_to_exactly_the_three_distinct_constraints() -> None:
    assert expand_constraints((Constraint(type="sudoku"),)) == [
        Constraint(type="rows-distinct"),
        Constraint(type="cols-distinct"),
        Constraint(type="regions-distinct"),
    ]


def test_sudoku_and_the_explicit_three_share_one_canonical_identity() -> None:
    preset = (Constraint(type="sudoku"),)
    explicit = (
        Constraint(type="rows-distinct"),
        Constraint(type="cols-distinct"),
        Constraint(type="regions-distinct"),
    )

    assert canonical_identity(preset) == canonical_identity(explicit)


def test_canonical_identity_is_order_independent() -> None:
    # Set-based identity: the same constraints spelled in any order collapse.
    forward = (Constraint(type="rows-distinct"), Constraint(type="cols-distinct"))
    reversed_ = (Constraint(type="cols-distinct"), Constraint(type="rows-distinct"))

    assert canonical_identity(forward) == canonical_identity(reversed_)


def test_two_constraints_of_one_type_resolve_to_a_single_layer_instance() -> None:
    # Dedup by type (issue #65): a puzzle with two cages of the same kind
    # resolves to one layer that loops its own constraints, not twice.
    constraints = (Constraint(type="rows-distinct"), Constraint(type="rows-distinct"))

    assert resolve_constraints(constraints) == [LAYER_REGISTRY["rows-distinct"]]


def test_unknown_constraint_type_is_rejected() -> None:
    with pytest.raises(UnknownLayerError):
        resolve_constraints((Constraint(type="not-a-real-rule"),))
