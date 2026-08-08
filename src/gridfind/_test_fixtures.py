"""Test data shared by more than one test module.

A plain module, not a `conftest.py`: pytest imports `conftest.py` under its own
name, so importing it a second time as `gridfind.conftest` would load the file
twice. This holds the fixtures that `sudokumaker_test` and `cli_test` both need,
so neither test module has to import the other.
"""

# The confirmed §4a classic link (issue #54). One link carries the whole
# positive corpus: given R1C6/R4C3/R7C2/R7C6, a placement at R1C1, a multi-digit
# center mark at R2C9 (`candidates 518 = 2^1+2^2+2^9`), a singleton center mark
# at R6C8 (`candidates 4 = 2^2`), and corner marks at R1C7-9 that map nowhere.
CLASSIC_LINK = (
    "https://sudokumaker.app/?puzzle="
    "N4IgZg9gTgtghgFwGoFMoGcCWEB2IBcIAjAHQCsJADCADQgAOArgF7MA2KBoOcMnhtEHEYIAFtA"
    "IgAwqMw4Aygihx6ggMYo2bdAQDaoAG5w2jfgHYAvjWBWb127ZABzTAZR58S03SMn%2BAFkc1aBw"
    "0AAV3NUw2AFk4KABrHXwADiCQ8MjouMTktOsQYKhQqAicKNj4pIJ8uzqHe0b6grU4HAATTHbEFG"
    "SyIlqG5uGh0YKXNw8vFB9jUwIyMZGmpdWV9eXhwrbO7oRegkCN51d3AmnZvwIANjXQCbPPKG8QX"
    "3nUu8%2BNr83RgF06MEcOglHA5AhkvoQAgAJ70fiURyw%2BEEIh0KAoFy4SGUGi43Fowk0ABMJL"
    "J%2BLxNCJaNJtMpFOpZLpAGYaKzWf4aJzOWQaLzeey2VzhTy%2BWLBRyRWL%2BTRrrL5WYaIrFSk"
    "aKrVXLNUrtSq1XqtXLldr1Wq-hYzRYgA"
)
