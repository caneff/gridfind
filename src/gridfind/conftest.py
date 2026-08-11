"""Test data shared by more than one test module in this package.

`cli_test` and `sudokumaker_test` both need the classic SudokuMaker link. It
lives here as a fixture so neither test module imports the other, matching
`layers/conftest.py`, which shares an assertion helper the same way. A
`conftest.py` is also the shape the wheel already excludes
(`pyproject.toml` `source-exclude`), so shared test data stays out of the
installed package.

`JIGSAW_TETROMINOES` is plain data, not a fixture — `layers/conftest.py`'s
docstring already makes the case that a fixture whose whole body is `return
_f` buys nothing over an import, and the same holds for a constant.
"""

import pytest

# A connected tetromino partition of a 4x4 board — deliberately not box
# tiling (which would be four 2x2 quadrants). `verdict_test.py` and
# `witness_validator_test.py` both need a regions-distinct partition a
# box-tiling fallback could not produce by accident (issue #207); sharing
# one definition keeps them from silently drifting into the box shape a
# typo could produce.
JIGSAW_TETROMINOES = [
    0, 0, 0, 1,
    0, 1, 1, 1,
    2, 2, 3, 3,
    2, 2, 3, 3,
]  # fmt: skip

# A found 4x4 sudoku-shaped partial (rows/cols/regions-distinct box tiling),
# two givens, no working-state placements. `cli_test` materializes it as a
# file to drive the file-path/stdin front door; `witness_validator_test`
# builds the `Puzzle`/`WorkingState` directly to exercise `validate_witness`'s
# box-aware rendering path (issue #207). Shared so the two can't drift into
# testing subtly different 4x4 boards (issue #246).
FOUND_4X4_DOC: dict[str, object] = {
    "puzzle": {
        "board": {"size": 4},
        "constraints": [
            {"type": "rows-distinct"},
            {"type": "cols-distinct"},
            {"type": "regions-distinct"},
        ],
        "givens": [
            {"address": "R1C1", "digit": 1},
            {"address": "R3C3", "digit": 2},
        ],
    },
    "working_state": {"places": [], "candidates": []},
}


@pytest.fixture
def classic_link() -> str:
    """The confirmed §4a classic link (issue #54).

    One link carries the whole positive corpus: given R1C6/R4C3/R7C2/R7C6, a
    placement at R1C1, a multi-digit center mark at R2C9 (`candidates 518 =
    2^1+2^2+2^9`), a singleton center mark at R6C8 (`candidates 4 = 2^2`), and
    corner marks at R1C7-9 that map nowhere.
    """
    return (
        "https://sudokumaker.app/?puzzle="
        "N4IgZg9gTgtghgFwGoFMoGcCWEB2IBcIAjAHQCsJADCADQgAOArgF7MA2KBoOcMnhtEHEYIAFtA"
        "IgAwqMw4Aygihx6ggMYo2bdAQDaoAG5w2jfgHYAvjWBWb127ZABzTAZR58S03SMn%2BAFkc1aBw"
        "0AAV3NUw2AFk4KABrHXwADiCQ8MjouMTktOsQYKhQqAicKNj4pIJ8uzqHe0b6grU4HAATTHbEFG"
        "SyIlqG5uGh0YKXNw8vFB9jUwIyMZGmpdWV9eXhwrbO7oRegkCN51d3AmnZvwIANjXQCbPPKG8QX"
        "3nUu8%2BNr83RgF06MEcOglHA5AhkvoQAgAJ70fiURyw%2BEEIh0KAoFy4SGUGi43Fowk0ABMJL"
        "J%2BLxNCJaNJtMpFOpZLpAGYaKzWf4aJzOWQaLzeey2VzhTy%2BWLBRyRWL%2BTRrrL5WYaIrFSk"
        "aKrVXLNUrtSq1XqtXLldr1Wq-hYzRYgA"
    )
