"""Row-major raw cell index to `RxCy` address translation — SudokuMaker's own
`i // N`, `i % N` indexing scheme resolved through `cell_geometry.format_address`.
`cages.py` and `markers.py` read a block's raw `cells`/`thermometers` indices
through this seam rather than deriving the scheme themselves.
"""

from __future__ import annotations

from collections.abc import Iterable

from gridfind.cell_geometry import flat_index, format_address, row_col_of_index


def address(index: int, size: int) -> str:
    """The row-major address of a raw cell `index` on a `size`-wide board: index
    `18` on a 9-board is R3C1. Resolves the `i // N`, `i % N` scheme through
    `cell_geometry.row_col_of_index`, the shared home for the arithmetic."""
    return format_address(*row_col_of_index(index, size))


def addresses(indices: Iterable[int], size: int) -> list[str]:
    """`address` mapped over a cell-index list, order preserved — so a thermo
    path keeps bulb-first order and a cage's cells read row-major."""
    return [address(i, size) for i in indices]


def cell_index(row: int, col: int, size: int) -> int:
    """The row-major raw cell index of 1-based `RxCy` on a `size`-wide board —
    the inverse of `address`. R3C1 on a 9-board is index 18. Places a cell by
    row/column into SudokuMaker's flat `cells` array via `cell_geometry.flat_index`."""
    return flat_index(row, col, size)
