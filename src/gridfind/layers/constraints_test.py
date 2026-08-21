import pytest

from gridfind.engine import MalformedPuzzleError, build_engine
from gridfind.layers import build_stack
from gridfind.layers.board import GridCells
from gridfind.layers.conftest import all_different_groups
from gridfind.layers.distinct import DistinctOverGroups, cols, regions, rows
from gridfind.layers.door import UnknownLayerError
from gridfind.layers.outside_cells import OutsideCells
from gridfind.layers.pair_difference import differs_by
from gridfind.layers.pair_ratio import ratio_of
from gridfind.layers.pair_relation import PairRelation
from gridfind.layers.s_blind import SBlindLayerError
from gridfind.layers.schrodinger import Schrodinger
from gridfind.layers.thermo import Thermo
from gridfind.puzzle import Board, Constraint

BOARD = GridCells()
OUTSIDE_CELLS = OutsideCells()
ROWS_DISTINCT = DistinctOverGroups("rows-distinct", rows)
COLS_DISTINCT = DistinctOverGroups("cols-distinct", cols)
REGIONS_DISTINCT = DistinctOverGroups("regions-distinct", regions)
PAIR_RELATIONS = {"pair-difference": differs_by, "pair-ratio": ratio_of}


def test_bare_constraints_resolve_to_the_matching_layer_instances() -> None:
    constraints = (Constraint(type="rows-distinct"), Constraint(type="cols-distinct"))

    _, layers = build_stack(constraints, size=9)

    assert layers == [BOARD, OUTSIDE_CELLS, ROWS_DISTINCT, COLS_DISTINCT]


def test_sudoku_preset_expands_to_exactly_the_three_distinct_constraints() -> None:
    canonical, _ = build_stack((Constraint(type="sudoku"),), size=9)

    assert canonical == [
        Constraint(type="rows-distinct"),
        Constraint(type="cols-distinct"),
        Constraint(type="regions-distinct"),
    ]


def test_two_constraints_of_one_type_resolve_to_a_single_layer_instance() -> None:
    # Dedup by type: a puzzle with two cages of the same kind
    # resolves to one layer that loops its own constraints, not twice.
    constraints = (Constraint(type="rows-distinct"), Constraint(type="rows-distinct"))

    _, layers = build_stack(constraints, size=9)

    assert layers == [BOARD, OUTSIDE_CELLS, ROWS_DISTINCT]


def test_regions_distinct_with_params_dispatches_over_the_supplied_map() -> None:
    # A `regions-distinct` carrying `params["regions"]` builds a
    # `DistinctOverGroups` over the setter's own partition, not the box
    # tiling — the label matrix groups R1C1+R2C2 and R1C2+R2C1, a partition
    # no box convention would produce.
    constraint = Constraint(type="regions-distinct", params={"regions": [0, 1, 1, 0]})

    _, layers = build_stack((constraint,), size=2)
    engine = build_engine([GridCells(), *layers], board=Board(size=2))

    groups = [sorted(g) for g in all_different_groups(engine)]
    assert sorted(groups) == [["R1C1", "R2C2"], ["R1C2", "R2C1"]]


def test_regions_distinct_with_no_params_still_dispatches_the_box_default() -> None:
    # No `params["regions"]` still resolves to the registry's shared,
    # box-tiling layer instance — a classic sudoku is unchanged.
    _, layers = build_stack((Constraint(type="regions-distinct"),), size=9)

    assert layers == [BOARD, OUTSIDE_CELLS, REGIONS_DISTINCT]


def test_regions_distinct_with_a_malformed_matrix_raises() -> None:
    constraint = Constraint(type="regions-distinct", params={"regions": [0, 1, 1]})

    with pytest.raises(MalformedPuzzleError):
        build_stack((constraint,), size=2)


def test_extra_region_dispatches_to_a_distinct_over_groups() -> None:
    # AC3: an `extra-region` block rides the same `DistinctOverGroups` rule
    # rows/cols/regions do — its cells fed as one partition group — not a rule
    # of its own. Asserted like `regions-distinct` with a supplied map: the
    # built rule is a `DistinctOverGroups`, its group the block's cells.
    constraint = Constraint(
        type="extra-region", params={"cells": ["R1C1", "R2C2", "R3C3", "R4C4"]}
    )

    canonical, layers = build_stack((constraint,), size=4)

    assert [type(layer) for layer in layers] == [
        GridCells,
        OutsideCells,
        DistinctOverGroups,
    ]
    assert layers[2].name == "extra-region"
    engine = build_engine(layers, tuple(canonical), board=Board(size=4))
    groups = [sorted(g) for g in all_different_groups(engine)]
    assert groups == [["R1C1", "R2C2", "R3C3", "R4C4"]]


def test_two_extra_region_constraints_fold_into_one_distinct_partition() -> None:
    # A windoku puzzle draws several windows, each its own `type 305` block.
    # AC3 folds them into one `DistinctOverGroups` — every window keeps its own
    # group in the one combined partition; several windows never collapse to a
    # single group.
    constraints = (
        Constraint(type="extra-region", params={"cells": ["R1C1", "R1C2"]}),
        Constraint(type="extra-region", params={"cells": ["R3C3", "R3C4"]}),
    )

    canonical, layers = build_stack(constraints, size=4)

    assert [type(layer) for layer in layers] == [
        GridCells,
        OutsideCells,
        DistinctOverGroups,
    ]
    engine = build_engine(layers, tuple(canonical), board=Board(size=4))
    groups = sorted(sorted(g) for g in all_different_groups(engine))
    assert groups == [["R1C1", "R1C2"], ["R3C3", "R3C4"]]


def test_unknown_constraint_type_is_rejected() -> None:
    with pytest.raises(UnknownLayerError):
        build_stack((Constraint(type="not-a-real-rule"),), size=9)


@pytest.mark.parametrize(
    "s_blind_type",
    ["anti-knight", "anti-king"],
)
def test_an_s_blind_layer_stacked_with_a_widening_layer_is_refused(
    s_blind_type: str,
) -> None:
    # Each of these reads a cell's single content slot, which has no defined
    # meaning once schrodinger widens every cell to two.
    constraints = (Constraint(type=s_blind_type), Constraint(type="schrodinger"))

    with pytest.raises(SBlindLayerError, match=s_blind_type):
        build_stack(constraints, size=9)


@pytest.mark.parametrize("pair_relation_type", ["pair-difference", "pair-ratio"])
def test_a_pair_relation_layer_composes_with_a_widening_layer(
    pair_relation_type: str,
) -> None:
    # Both kropki pair layers read `engine.value_expr`, not a cell's single
    # content slot, so they carry no `s_blind` flag and stack freely with
    # schrodinger — unlike anti-knight/anti-king above.
    constraints = (Constraint(type=pair_relation_type), Constraint(type="schrodinger"))

    _, layers = build_stack(constraints, size=9)

    assert layers == [
        BOARD,
        OUTSIDE_CELLS,
        PairRelation(pair_relation_type, relation=PAIR_RELATIONS[pair_relation_type]),
        Schrodinger(),
    ]


def test_thermo_composes_with_a_widening_layer() -> None:
    # thermo reads engine.value_expr like the pair-relation family, so it
    # carries no `s_blind` flag and stacks freely with schrodinger.
    constraints = (Constraint(type="thermo"), Constraint(type="schrodinger"))

    _, layers = build_stack(constraints, size=9)

    assert layers == [BOARD, OUTSIDE_CELLS, Thermo(), Schrodinger()]


def test_an_s_blind_layer_alone_is_unaffected() -> None:
    # No widening layer in the stack: an s-blind layer is perfectly fine on
    # its own.
    _, layers = build_stack((Constraint(type="anti-knight"),), size=9)

    assert len(layers) == 3


def test_a_widening_layer_alone_is_unaffected() -> None:
    _, layers = build_stack((Constraint(type="schrodinger"),), size=9)

    assert len(layers) == 3


def test_no_constraints_still_carries_the_compulsory_board_layer() -> None:
    canonical, layers = build_stack((), size=9)

    assert canonical == []
    assert layers == [BOARD, OUTSIDE_CELLS]


def test_a_board_constraint_dedups_onto_the_one_compulsory_board_layer() -> None:
    # Naming `board` as a constraint resolves to the one compulsory board
    # layer, not a second grid registration.
    canonical, layers = build_stack((Constraint(type="board"),), size=9)

    assert canonical == [Constraint(type="board")]
    assert layers == [BOARD, OUTSIDE_CELLS]


def test_a_board_constraint_builds_one_grid_with_no_unruled_variables() -> None:
    # Naming `board` builds exactly one grid's worth of solver variables for
    # one grid of cells, not two.
    canonical, layers = build_stack((Constraint(type="board"),), size=4)
    engine = build_engine(layers, tuple(canonical), board=Board(size=4))

    assert len(engine.cells) == 16
    assert len(engine.model.proto.variables) == 16


@pytest.mark.parametrize("alias", ["x", "v"], ids=["x-alias", "v-alias"])
def test_alias_refuses_a_clue_that_also_states_the_sum_it_fixes(alias: str) -> None:
    # An X (or V) clue names its own sum via the alias; a clue that also
    # spells out "sum" is a contradiction, not a silent overwrite.
    constraint = Constraint(type=alias, params={"cells": ["R1C1", "R1C2"], "sum": 99})

    with pytest.raises(MalformedPuzzleError, match=f"{alias!r}.*sum"):
        build_stack((constraint,), size=9)


def test_alias_with_only_its_own_params_still_expands() -> None:
    # The cells param is not fixed by the alias, so it passes through — only
    # the genuine contradiction (restating "sum") is refused.
    constraint = Constraint(type="x", params={"cells": ["R1C1", "R1C2"]})

    canonical, _ = build_stack((constraint,), size=9)

    assert canonical == [
        Constraint(type="group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 10})
    ]
