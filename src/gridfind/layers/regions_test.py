import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from gridfind.engine import GridfindError, MalformedPuzzleError
from gridfind.layers.regions import RegionMap, box_regions, region_map_for

BOARD_SIZE = 9


# Spelled out rather than read from BOX_SHAPE on purpose: an independent
# statement of the convention, so a typo in the table fails a test instead of
# being copied into the expectation.
@pytest.mark.parametrize(
    ("size", "box_rows", "box_cols"),
    [
        pytest.param(4, 2, 2, id="4x4-tiles-2x2"),
        pytest.param(6, 2, 3, id="6x6-tiles-2x3"),
        pytest.param(9, 3, 3, id="9x9-tiles-3x3"),
    ],
)
def test_box_regions_tiles_the_board_and_covers_every_cell_once(
    size: int, box_rows: int, box_cols: int
) -> None:
    # Every size tiles into `size` regions of `size` cells that partition the
    # board — a 6x6 as six 2x3 boxes, never as four 3x3 quattro quadri. The
    # coverage half is what a count-only assertion misses: a partition that
    # duplicated one cell and dropped another would still count right.
    region_map = box_regions(size, box_rows, box_cols)
    every_cell = [
        (row, col) for row in range(1, size + 1) for col in range(1, size + 1)
    ]

    assert len(region_map) == size
    for region in region_map:
        assert len(region) == size
    assert sorted(cell for region in region_map for cell in region) == every_cell


def test_region_map_for_falls_back_to_the_boards_box_tiling() -> None:
    # With no setter-supplied map, the box convention is the default source:
    # a 6x6 comes back tiled 2x3, R1C1's box holding its two rows of three.
    region_map = region_map_for(6)

    assert len(region_map) == 6
    assert region_map[0] == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]


def test_region_map_for_refuses_a_size_with_no_box_convention() -> None:
    # The refusal lives on the fallback: only a board asking to be tiled by
    # convention needs a convention to exist.
    with pytest.raises(GridfindError):
        region_map_for(5)


def test_region_map_round_trips_through_labels_up_to_relabeling() -> None:
    # to_labels/from_labels round-trip group membership, not the original
    # label values or region order — sorted comparison is the honest
    # assertion of that contract.
    region_map = box_regions(4, 2, 2)

    rebuilt = RegionMap.from_labels(4, region_map.to_labels(4))

    assert sorted(rebuilt) == sorted(region_map)


def test_region_map_from_labels_groups_arbitrary_noncontiguous_labels() -> None:
    # A 2x2 board split by label 7 (top row) and label 2 (bottom row) — ids
    # need not be contiguous or start at 0, and sizes need not match.
    labels = [7, 7, 2, 2]

    region_map = RegionMap.from_labels(2, labels)

    assert sorted(region_map) == [[(1, 1), (1, 2)], [(2, 1), (2, 2)]]


def test_region_map_from_labels_groups_a_noncontiguous_regions_cells() -> None:
    # One label's cells need not be adjacent — a region is whatever shares an
    # id, wherever it sits on the board.
    labels = [0, 1, 1, 0]

    region_map = RegionMap.from_labels(2, labels)

    assert sorted(region_map) == [[(1, 1), (2, 2)], [(1, 2), (2, 1)]]


def test_region_map_from_labels_accepts_unequal_region_sizes() -> None:
    labels = [0, 0, 0, 1]

    region_map = RegionMap.from_labels(2, labels)

    assert sorted(len(region) for region in region_map) == [1, 3]


def test_region_map_from_labels_refuses_the_wrong_length() -> None:
    with pytest.raises(MalformedPuzzleError):
        RegionMap.from_labels(2, [0, 0, 0])


def test_region_map_from_labels_refuses_a_non_list() -> None:
    with pytest.raises(MalformedPuzzleError):
        RegionMap.from_labels(2, "0001")


def test_region_map_from_labels_refuses_a_non_integer_entry() -> None:
    with pytest.raises(MalformedPuzzleError):
        RegionMap.from_labels(2, [0, 0, 0, "a"])


@given(labels=st.lists(st.integers(), min_size=0, max_size=30))
def test_region_map_from_labels_refuses_any_wrong_length(labels: list[int]) -> None:
    size = 4
    assume(len(labels) != size * size)
    with pytest.raises(MalformedPuzzleError):
        RegionMap.from_labels(size, labels)
