"""Link-synthesis primitives shared by the per-module decode tests.

Every `sudokumaker/*_test.py` builds its input the same way: a puzzle document
encoded to a real SudokuMaker link through `document_to_link`, then run through
`decode_link`. The synthesis pieces above that boundary — the document wrapper,
the classic `type 0`/`type 1` constraint pair, the empty 9x9 cell array, the box
partition of an N x N board — are needed by more than one module's test file, so
they live here as one home rather than drifting into per-file copies.

A `conftest.py` is excluded from the built wheel (`pyproject.toml`
`source-exclude`), so this test-only synthesis stays out of the installed
package. Following `layers/conftest.py`, the shared pieces are plain
constants and functions, not `return _f` fixtures.
"""

from gridfind.puzzle import Constraint
from gridfind.sudokumaker.boundary import document_to_link


def regions_for(n: int, box_rows: int, box_cols: int) -> list[int]:
    """The standard box partition of an n x n board as a flat row-major id
    array, derived independently of the decoder (region = band-row * bands +
    band-col)."""
    bands = n // box_cols
    return [
        (r // box_rows) * bands + (c // box_cols) for r in range(n) for c in range(n)
    ]


# The classic decode's constraint tuple, in the order the decoder emits it.
CLASSIC_CONSTRAINTS = (
    Constraint("rows-distinct"),
    Constraint("cols-distinct"),
    Constraint("regions-distinct"),
)

# The standard 3x3 box id per cell of a 9x9 board — the n=9 case of the general
# partition, derived independently of the decoder's own region map.
STANDARD_REGIONS = regions_for(9, 3, 3)

# An empty 9x9 cell array — the blank canvas every classic-size link starts from.
EMPTY_CELLS: list[dict[str, object]] = [{} for _ in range(81)]

# A jigsaw 9x9 region matrix: R1C1 moved out of its box, so it differs from the
# standard partition and rides onto the constraint's params.
JIGSAW_REGIONS = [8, *STANDARD_REGIONS[1:]]

# SudokuMaker's own classic wire vocabulary — its constraint blocks, not
# gridfind's `Constraint`: the implicit `type 0` givens block and a `type 1`
# regions block whose matrix is the standard boxes.
WIRE_CONSTRAINTS: list[dict[str, object]] = [
    {"type": 0},
    {"type": 1, "regions": STANDARD_REGIONS},
]


def encode_document(puzzle: dict[str, object]) -> str:
    """A synthesised bare link: the `puzzle` block wrapped in a
    `formatVersion 1.5.0` document and encoded through `document_to_link`, the
    one home for the compress-to-payload step."""
    return document_to_link({"formatVersion": "1.5.0", "puzzle": puzzle})


def constraint_link(constraint: dict[str, object]) -> str:
    """A classic 9x9 link carrying one extra `constraint` block alongside the
    standard givens/regions pair."""
    return encode_document(
        {"cells": EMPTY_CELLS, "constraints": [*WIRE_CONSTRAINTS, constraint]}
    )


def mask(digits: set[int]) -> int:
    """The `candidates` bitmask SudokuMaker writes for a set of center marks:
    bit `d` set for each digit `d`."""
    total = 0
    for d in digits:
        total |= 1 << d
    return total
