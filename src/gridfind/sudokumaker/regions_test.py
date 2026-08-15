"""`regions`: the `type 1` box-partition block and its absence.

No `type 1` means the setter asked for no regions — a Latin square on rows and
columns alone, never invented boxes. A `type 1` matrix equal to the standard
box tiling decodes to a bare `regions-distinct`; one that differs (a jigsaw)
carries its own matrix onto the constraint's `params["regions"]`.
"""

from gridfind.puzzle import Board, Constraint
from gridfind.sudokumaker import decode_link
from gridfind.sudokumaker.conftest import (
    EMPTY_CELLS,
    JIGSAW_REGIONS,
    encode_document,
    regions_for,
)


def test_link_without_type_one_is_a_latin_square() -> None:
    # No `type 1` regions block means the setter asked for no regions — rows and
    # columns distinct only. gridfind must not invent boxes (the box tiling is
    # supplied only when the link carries the box matrix). A real boxed
    # SudokuMaker puzzle always ships its boxes as an explicit `type 1`.
    payload = encode_document({"cells": EMPTY_CELLS, "constraints": [{"type": 0}]})

    puzzle, _ = decode_link(payload)

    assert puzzle.constraints == (
        Constraint("rows-distinct"),
        Constraint("cols-distinct"),
    )


def test_untileable_latin_square_decodes() -> None:
    # A 5x5 has no box convention, but with no `type 1` it needs none — it is a
    # 5x5 Latin square, answerable on rows and columns alone, not a link to
    # refuse.
    payload = encode_document(
        {"cells": [{} for _ in range(25)], "size": 5, "constraints": [{"type": 0}]}
    )

    puzzle, _ = decode_link(payload)

    assert puzzle.board == Board(size=5)
    assert all(c.type != "regions-distinct" for c in puzzle.constraints)


def test_non_nine_jigsaw_matrix_rides_onto_constraint_params() -> None:
    # A 6x6 type-1 matrix that isn't the 2x3 convention tiling carries verbatim
    # onto params["regions"] (generalized to non-9).
    standard_6 = regions_for(6, 2, 3)
    # Move R1C1 into R1C4's box (0 -> 1): a real jigsaw, not a within-box swap.
    jigsaw_6 = [standard_6[3], *standard_6[1:]]
    payload = encode_document(
        {
            "cells": [{} for _ in range(36)],
            "size": 6,
            "constraints": [{"type": 0}, {"type": 1, "regions": jigsaw_6}],
        }
    )

    puzzle, _ = decode_link(payload)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint.params == {"regions": jigsaw_6}


def test_non_nine_standard_matrix_stays_bare() -> None:
    # A 6x6 type-1 matrix equal to the 2x3 convention tiling emits a bare
    # regions-distinct, just as the classic 9x9 case does.
    payload = encode_document(
        {
            "cells": [{} for _ in range(36)],
            "size": 6,
            "constraints": [{"type": 0}, {"type": 1, "regions": regions_for(6, 2, 3)}],
        }
    )

    puzzle, _ = decode_link(payload)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint == Constraint("regions-distinct")


def test_jigsaw_regions_decode_into_constraint_params() -> None:
    # A type 1 link whose regions differ from the standard 3x3 partition decodes
    # with the setter's own matrix carried on the regions-distinct constraint's
    # params.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [{"type": 0}, {"type": 1, "regions": JIGSAW_REGIONS}],
        }
    )

    puzzle, _ = decode_link(payload)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint.params == {"regions": JIGSAW_REGIONS}
