import pytest

from gridfind.layers import (
    LAYER_REGISTRY,
    UnknownLayerError,
    canonical_identity,
    expand_records,
    resolve_records,
)
from gridfind.puzzle import Variant


def test_bare_records_resolve_to_the_matching_layer_instances() -> None:
    records = (Variant(type="rows-distinct"), Variant(type="cols-distinct"))

    assert resolve_records(records) == [
        LAYER_REGISTRY["rows-distinct"],
        LAYER_REGISTRY["cols-distinct"],
    ]


def test_sudoku_sugar_expands_to_exactly_the_three_distinct_records() -> None:
    assert expand_records((Variant(type="sudoku"),)) == [
        Variant(type="rows-distinct"),
        Variant(type="cols-distinct"),
        Variant(type="regions-distinct"),
    ]


def test_sudoku_and_the_explicit_three_share_one_canonical_identity() -> None:
    sugar = (Variant(type="sudoku"),)
    explicit = (
        Variant(type="rows-distinct"),
        Variant(type="cols-distinct"),
        Variant(type="regions-distinct"),
    )

    assert canonical_identity(sugar) == canonical_identity(explicit)


def test_canonical_identity_is_order_independent() -> None:
    # Set-based identity: the same constraints spelled in any order collapse.
    forward = (Variant(type="rows-distinct"), Variant(type="cols-distinct"))
    reversed_ = (Variant(type="cols-distinct"), Variant(type="rows-distinct"))

    assert canonical_identity(forward) == canonical_identity(reversed_)


def test_two_records_of_one_type_resolve_to_a_single_layer_instance() -> None:
    # Dedup by type (issue #65): a puzzle with two cages of the same kind
    # resolves to one layer that loops its own records, not the layer twice.
    records = (Variant(type="rows-distinct"), Variant(type="rows-distinct"))

    assert resolve_records(records) == [LAYER_REGISTRY["rows-distinct"]]


def test_unknown_record_type_is_rejected() -> None:
    with pytest.raises(UnknownLayerError):
        resolve_records((Variant(type="not-a-real-rule"),))
