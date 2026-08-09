import pytest

from gridfind.engine import GridfindError, MissingDependencyError, build_engine
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import all_different_groups
from gridfind.layers.distinct import (
    DistinctOverGroups,
    cols,
    regions,
    regions_from,
    rows,
)
from gridfind.layers.schrodinger import Schrodinger
from gridfind.puzzle import Board

_PARTITIONS = {
    "rows-distinct": rows,
    "cols-distinct": cols,
    "regions-distinct": regions,
}


def _grid(size: int) -> list[list[str]]:
    # Each cell a unique label so a partition's groups are identifiable.
    return [[f"r{r}c{c}" for c in range(size)] for r in range(size)]


def test_cols_partition_is_the_transpose() -> None:
    grid = _grid(4)

    assert [list(col) for col in cols(grid)] == [
        ["r0c0", "r1c0", "r2c0", "r3c0"],
        ["r0c1", "r1c1", "r2c1", "r3c1"],
        ["r0c2", "r1c2", "r2c2", "r3c2"],
        ["r0c3", "r1c3", "r2c3", "r3c3"],
    ]


def test_regions_partition_covers_every_cell_exactly_once() -> None:
    # Size-agnostic via BOX_SHAPE — a 6x6 tiles as six 2x3 boxes, never as
    # four 3x3 mini-grids, together the whole grid with no cell repeated.
    grid = _grid(6)
    groups = [list(g) for g in regions(grid)]

    assert len(groups) == 6
    for group in groups:
        assert len(group) == 6
    flat = [cell for group in groups for cell in group]
    assert sorted(flat) == sorted(cell for row in grid for cell in row)


def test_regions_raises_for_a_board_size_with_no_classic_box_convention() -> None:
    with pytest.raises(GridfindError):
        list(regions(_grid(5)))


def test_regions_first_region_is_the_top_left_3x3_box() -> None:
    grid = _grid(9)

    assert set(next(iter(regions(grid)))) == {
        "r0c0",
        "r0c1",
        "r0c2",
        "r1c0",
        "r1c1",
        "r1c2",
        "r2c0",
        "r2c1",
        "r2c2",
    }


def test_regions_from_cuts_the_grid_by_the_supplied_map() -> None:
    # A partition function built from a setter-supplied map, not the box
    # convention (issue #123) — a jigsaw region here spans two rows.
    grid = _grid(2)
    supplied = [[(1, 1), (2, 2)], [(1, 2), (2, 1)]]

    groups = [sorted(g) for g in regions_from(supplied)(grid)]

    assert sorted(groups) == [["r0c0", "r1c1"], ["r0c1", "r1c0"]]


@pytest.mark.parametrize("name", ["rows-distinct", "cols-distinct", "regions-distinct"])
def test_distinct_layer_requires_board(name: str) -> None:
    with pytest.raises(MissingDependencyError):
        build_engine([DistinctOverGroups(name, _PARTITIONS[name])], board=Board(size=9))


@pytest.mark.parametrize(
    ("name", "first_group"),
    [
        ("rows-distinct", [f"R1C{col}" for col in range(1, 10)]),
        ("cols-distinct", [f"R{row}C1" for row in range(1, 10)]),
        (
            "regions-distinct",
            [f"R{row}C{col}" for row in (1, 2, 3) for col in (1, 2, 3)],
        ),
    ],
    ids=["rows", "cols", "regions"],
)
def test_distinct_layer_emits_one_all_different_rule_per_group(
    name: str,
    first_group: list[str],
) -> None:
    """Which cells each group holds, not merely how many. The first group is
    the partition's own first cut — row 1, column 1, the top-left region."""
    engine = build_engine(
        [GridCells(), DistinctOverGroups(name, _PARTITIONS[name])], board=Board(size=9)
    )

    groups = all_different_groups(engine)

    assert len(groups) == 9
    assert all(len(group) == 9 for group in groups)
    assert sorted(groups[0]) == sorted(first_group)


def test_distinct_layer_skips_all_different_when_schrodinger_widens_the_cells() -> None:
    # With `schrodinger` in the stack, DistinctOverGroups routes through the
    # is_S-gated counting rule (issue #141) instead — no add_all_different at
    # all, so a non-schrodinger puzzle's model stays untouched (no-regression).
    engine = build_engine(
        [GridCells(), Schrodinger(), DistinctOverGroups("rows-distinct", rows)],
        board=Board(size=4, values=range(5)),
    )

    assert all_different_groups(engine) == []
