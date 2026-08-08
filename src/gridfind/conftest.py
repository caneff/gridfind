"""Test data shared by more than one test module in this package.

`cli_test` and `sudokumaker_test` both need the classic SudokuMaker link. It
lives here as a fixture so neither test module imports the other, matching
`layers/conftest.py`, which shares an assertion helper the same way. A
`conftest.py` is also the shape the wheel already excludes
(`pyproject.toml` `source-exclude`), so shared test data stays out of the
installed package.
"""

import pytest


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
