import gridfind.layers
from gridfind.layers import LAYER_REGISTRY
from gridfind.layers.distinct import DistinctOverGroups


def test_public_api_surface_is_exactly_the_committed_names() -> None:
    # Issue #25 / #24: gridfind.layers is internal-only, so its committed public
    # surface is these names — the record dispatch API (#47). Registries and
    # layer classes are internal. #48 deleted the old string stack API
    # (expand_stack, resolve, the preset registry).
    assert gridfind.layers.__all__ == [
        "UnknownLayerError",
        "canonical_identity",
        "expand_records",
        "resolve_records",
    ]


def test_rows_cols_regions_are_all_one_distinct_layer_class() -> None:
    # Issue #37: the three distinct rules are instances of one
    # partition-parameterized layer, not three bespoke classes.
    for name in ("rows-distinct", "cols-distinct", "regions-distinct"):
        assert isinstance(LAYER_REGISTRY[name], DistinctOverGroups)
        assert LAYER_REGISTRY[name].name == name


def test_the_hardcoded_irregular_demo_entry_is_gone() -> None:
    # Issue #37 (Q3): the one hardcoded irregular board is dropped; setter-
    # supplied region maps come back through params later (parked #30).
    assert "regions-distinct-irregular" not in LAYER_REGISTRY
