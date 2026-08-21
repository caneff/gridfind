from gridfind.layers.regions import RegionMap, box_regions
from gridfind.witness import Witness


def test_witness_render_draws_jigsaw_borders_between_regions() -> None:
    # Two single-column regions on a 2x2 board: a vertical divider runs the
    # full height, no horizontal divider — junctions resolved from whichever
    # arms actually meet.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (1,),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (4,),
    }
    region_map = RegionMap([[(1, 1), (2, 1)], [(1, 2), (2, 2)]])
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == ("┌───┬───┐\n│ 1 │ 2 │\n│   │   │\n│ 3 │ 4 │\n└───┴───┘")


def test_witness_render_draws_classic_box_borders_for_a_box_partition() -> None:
    # Fed the classic box tiling, the same renderer draws the familiar 3x3-
    # style boxes — here a 4x4's 2x2 boxes.
    grid = [[f"R{r}C{c}" for c in range(1, 5)] for r in range(1, 5)]
    assignment: dict[str, tuple[int, ...]] = {
        address: (i % 9 + 1,) for i, row in enumerate(grid) for address in row
    }
    witness = Witness(grid=grid, assignment=assignment, region_map=box_regions(4, 2, 2))

    assert witness.render() == (
        "┌───────┬───────┐\n"
        "│ 1   1 │ 1   1 │\n"
        "│       │       │\n"
        "│ 2   2 │ 2   2 │\n"
        "├───────┼───────┤\n"
        "│ 3   3 │ 3   3 │\n"
        "│       │       │\n"
        "│ 4   4 │ 4   4 │\n"
        "└───────┴───────┘"
    )


def test_witness_render_draws_singleton_and_unequal_regions_correctly() -> None:
    # A singleton region beside an 8-cell region on a 3x3 board — no
    # nine-of-nine assumption.
    grid = [[f"R{r}C{c}" for c in range(1, 4)] for r in range(1, 4)]
    assignment: dict[str, tuple[int, ...]] = {
        address: (i % 9 + 1,) for i, row in enumerate(grid) for address in row
    }
    region_map = RegionMap(
        [
            [(1, 1)],
            [(1, 2), (1, 3), (2, 1), (2, 2), (2, 3), (3, 1), (3, 2), (3, 3)],
        ]
    )
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == (
        "┌───┬───────┐\n"
        "│ 1 │ 1   1 │\n"
        "├───┘       │\n"
        "│ 2   2   2 │\n"
        "│           │\n"
        "│ 3   3   3 │\n"
        "└───────────┘"
    )


def test_witness_render_draws_an_s_cell_as_a_curly_brace_pair() -> None:
    # An S-cell's pair widens the whole witness —
    # every cell, singleton or not, right-pads to the widest so columns stay
    # aligned and the box banding (still a two-region jigsaw here) survives.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (0, 5),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (1,),
    }
    region_map = RegionMap([[(1, 1), (2, 1)], [(1, 2), (2, 2)]])
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == (
        "┌───────┬───────┐\n"
        "│ {0 5} │     2 │\n"
        "│       │       │\n"
        "│     3 │     1 │\n"
        "└───────┴───────┘"
    )


def test_witness_render_draws_an_outside_cell_above_its_column() -> None:
    # An escape-the-grid outside cell rides in `assignment` off an address
    # `grid` never lays out (CONTEXT.md, "outside cell") — its own dot on the
    # border ring, one line above the box, aligned under its column.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (1,),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (4,),
        "R0C1": (9,),
    }
    region_map = RegionMap([[(1, 1), (2, 1)], [(1, 2), (2, 2)]])
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == (
        "     9         \n"
        "   ┌───┬───┐   \n"
        "   │ 1 │ 2 │   \n"
        "   │   │   │   \n"
        "   │ 3 │ 4 │   \n"
        "   └───┴───┘   \n"
        "               "
    )


def test_witness_render_draws_an_outside_cell_on_each_side_of_the_ring() -> None:
    # All four sides at once: top/bottom above and below their column, left/
    # right beside their row — a referenced side that isn't populated (no
    # outside cell created there) stays blank, never invented.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (1,),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (4,),
        "R0C1": (9,),
        "R0C2": (7,),
        "R1C0": (8,),
        "R2C3": (6,),
        "R3C2": (5,),
    }
    region_map = RegionMap([[(1, 1), (2, 1)], [(1, 2), (2, 2)]])
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == (
        "     9   7     \n"
        "   ┌───┬───┐   \n"
        " 8 │ 1 │ 2 │   \n"
        "   │   │   │   \n"
        "   │ 3 │ 4 │ 6 \n"
        "   └───┴───┘   \n"
        "         5     "
    )


def test_witness_render_draws_a_created_corner_outside_cell() -> None:
    # A corner outside cell (row/col both off the grid) is usually never
    # created — but when a clue genuinely names one, its solved value must
    # still print, not vanish off the edge of the ring the way a position
    # keyed only by an interior row/col would miss it.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (1,),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (4,),
        "R0C0": (9,),
        "R0C3": (7,),
        "R3C0": (6,),
        "R3C3": (5,),
    }
    region_map = RegionMap([[(1, 1), (2, 1)], [(1, 2), (2, 2)]])
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == (
        " 9           7 \n"
        "   ┌───┬───┐   \n"
        "   │ 1 │ 2 │   \n"
        "   │   │   │   \n"
        "   │ 3 │ 4 │   \n"
        "   └───┴───┘   \n"
        " 6           5 "
    )


def test_witness_render_is_unchanged_with_no_outside_cells() -> None:
    # No entry in `assignment` falls outside `grid` — the ring adds nothing,
    # byte-identical to the plain grid.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (1,),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (4,),
    }
    region_map = RegionMap([[(1, 1), (2, 1)], [(1, 2), (2, 2)]])
    witness = Witness(grid=grid, assignment=assignment, region_map=region_map)

    assert witness.render() == "┌───┬───┐\n│ 1 │ 2 │\n│   │   │\n│ 3 │ 4 │\n└───┴───┘"


def test_witness_identity_is_the_frozen_assignment_and_modifiers_tuple() -> None:
    # Hand-derived oracle (ADR-0015): the identity is the assignment and
    # modifiers dicts, each frozen into a tuple of their items in iteration
    # order — nothing sorted, nothing dropped. This is the one place the
    # formula stays spelled out as a cross-check on `.identity` itself.
    grid = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
    assignment: dict[str, tuple[int, ...]] = {
        "R1C1": (0, 5),
        "R1C2": (2,),
        "R2C1": (3,),
        "R2C2": (1,),
    }
    region_map = RegionMap([[(1, 1), (2, 1)], [(1, 2), (2, 2)]])
    modifiers = {"R2C2": "doubler"}
    witness = Witness(
        grid=grid,
        assignment=assignment,
        region_map=region_map,
        modifiers=modifiers,
    )

    assert witness.identity == (
        (
            ("R1C1", (0, 5)),
            ("R1C2", (2,)),
            ("R2C1", (3,)),
            ("R2C2", (1,)),
        ),
        (("R2C2", "doubler"),),
    )
