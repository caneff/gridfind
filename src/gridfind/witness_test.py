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
