import gridfind.layers
from gridfind.layers import LAYER_REGISTRY
from gridfind.layers.board import BOARD_SIZE
from gridfind.layers.regions import RegionsDistinct


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


def test_regions_distinct_irregular_registry_entry_uses_a_different_map() -> None:
    classic = LAYER_REGISTRY["regions-distinct"]
    irregular = LAYER_REGISTRY["regions-distinct-irregular"]

    assert isinstance(classic, RegionsDistinct)
    assert isinstance(irregular, RegionsDistinct)
    assert classic.region_map != irregular.region_map
    assert len(irregular.region_map) == BOARD_SIZE
    for region in irregular.region_map:
        assert len(region) == BOARD_SIZE
