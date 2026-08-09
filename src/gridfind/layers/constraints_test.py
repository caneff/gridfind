import pytest

from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers import UnknownLayerError, build_stack, canonical_identity
from gridfind.layers.board import GridCells
from gridfind.layers.distinct import DistinctOverGroups, cols, regions, rows
from gridfind.puzzle import Board, Constraint

BOARD = GridCells()
ROWS_DISTINCT = DistinctOverGroups("rows-distinct", rows)
COLS_DISTINCT = DistinctOverGroups("cols-distinct", cols)
REGIONS_DISTINCT = DistinctOverGroups("regions-distinct", regions)


def test_bare_constraints_resolve_to_the_matching_layer_instances() -> None:
    constraints = (Constraint(type="rows-distinct"), Constraint(type="cols-distinct"))

    _, layers = build_stack(constraints)

    assert layers == [BOARD, ROWS_DISTINCT, COLS_DISTINCT]


def test_rows_cols_regions_are_all_one_distinct_layer_class() -> None:
    # Issue #37: the three distinct rules are instances of one
    # partition-parameterized layer, not three bespoke classes.
    _, layers = build_stack(
        (
            Constraint(type="rows-distinct"),
            Constraint(type="cols-distinct"),
            Constraint(type="regions-distinct"),
        )
    )

    assert layers == [BOARD, ROWS_DISTINCT, COLS_DISTINCT, REGIONS_DISTINCT]


def test_sudoku_preset_expands_to_exactly_the_three_distinct_constraints() -> None:
    canonical, _ = build_stack((Constraint(type="sudoku"),))

    assert canonical == [
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

    _, layers = build_stack(constraints)

    assert layers == [BOARD, ROWS_DISTINCT]


def test_unknown_constraint_type_is_rejected() -> None:
    with pytest.raises(UnknownLayerError):
        build_stack((Constraint(type="not-a-real-rule"),))


def test_no_constraints_still_carries_the_compulsory_board_layer() -> None:
    canonical, layers = build_stack(())

    assert canonical == []
    assert layers == [BOARD]


def test_a_board_constraint_dedups_onto_the_one_compulsory_board_layer() -> None:
    # Issue #101 / #99 further notes: naming `board` as a constraint used to
    # register the grid a second time. It now resolves to the same one entry.
    canonical, layers = build_stack((Constraint(type="board"),))

    assert canonical == [Constraint(type="board")]
    assert layers == [BOARD]


def test_a_board_constraint_builds_one_grid_with_no_unruled_variables() -> None:
    # #99's further notes: naming `board` used to build two grids' worth of
    # solver variables for one grid of cells. It builds exactly one now.
    canonical, layers = build_stack((Constraint(type="board"),))
    engine = build_engine(layers, tuple(canonical), board=Board(size=4))

    assert len(engine.cells) == 16
    assert len(engine.model.proto.variables) == 16


@pytest.mark.parametrize("alias", ["x", "v"], ids=["x-alias", "v-alias"])
def test_alias_refuses_a_clue_that_also_states_the_sum_it_fixes(alias: str) -> None:
    # An X (or V) clue names its own sum via the alias; a clue that also
    # spells out "sum" is a contradiction, not a silent overwrite.
    constraint = Constraint(type=alias, params={"cells": ["R1C1", "R1C2"], "sum": 99})

    with pytest.raises(MalformedPuzzleError, match=f"{alias!r}.*sum"):
        build_stack((constraint,))


def test_alias_with_only_its_own_params_still_expands() -> None:
    # The cells param is not fixed by the alias, so it passes through — only
    # the genuine contradiction (restating "sum") is refused.
    constraint = Constraint(type="x", params={"cells": ["R1C1", "R1C2"]})

    canonical, _ = build_stack((constraint,))

    assert canonical == [
        Constraint(type="pair-sum", params={"cells": ["R1C1", "R1C2"], "sum": 10})
    ]
