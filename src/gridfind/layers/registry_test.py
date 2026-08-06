import pytest

from gridfind.layers import (
    LAYER_REGISTRY,
    PRESET_REGISTRY,
    RegionsDistinct,
    UnknownLayerError,
    resolve,
)
from gridfind.layers.board import BOARD_SIZE


def test_resolve_rejects_an_unregistered_layer_name() -> None:
    with pytest.raises(UnknownLayerError):
        resolve(["not-a-real-layer"])


def test_classic_sudoku_preset_resolves_to_the_full_sudoku_layer_list() -> None:
    assert PRESET_REGISTRY["classic-sudoku"] == [
        "board",
        "rows-distinct",
        "cols-distinct",
        "regions-distinct",
    ]

    preset_layers = resolve("classic-sudoku")
    explicit_layers = resolve(
        ["board", "rows-distinct", "cols-distinct", "regions-distinct"]
    )

    assert [layer.name for layer in preset_layers] == [
        layer.name for layer in explicit_layers
    ]


def test_resolve_rejects_an_unregistered_preset_name() -> None:
    with pytest.raises(UnknownLayerError):
        resolve("not-a-real-preset")


def test_regions_distinct_irregular_registry_entry_uses_a_different_map() -> None:
    classic = LAYER_REGISTRY["regions-distinct"]
    irregular = LAYER_REGISTRY["regions-distinct-irregular"]

    assert isinstance(classic, RegionsDistinct)
    assert isinstance(irregular, RegionsDistinct)
    assert classic.region_map != irregular.region_map
    assert len(irregular.region_map) == BOARD_SIZE
    for region in irregular.region_map:
        assert len(region) == BOARD_SIZE
