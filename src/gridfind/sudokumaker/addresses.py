"""Row-major raw cell index to `RxCy` address translation — SudokuMaker's own
`i // N`, `i % N` indexing scheme resolved through `cell_geometry.format_address`.
`cages.py` and `markers.py` read a block's raw `cells`/`thermometers` indices
through this seam rather than deriving the scheme themselves.
"""

from __future__ import annotations

from collections.abc import Iterable

from gridfind.cell_geometry import format_address, index_to_row_col


def index_to_address(index: int, size: int) -> str:
    """The row-major address of a raw cell `index` on a `size`-wide board: index
    `18` on a 9-board is R3C1. Resolves the `i // N`, `i % N` scheme through
    `cell_geometry.index_to_row_col`, the shared home for the arithmetic. One-way:
    the raw wire carries indices, and nothing reads an address string back to an
    index — a caller holding `(row, col)` uses `cell_geometry.row_col_to_index`."""
    return format_address(*index_to_row_col(index, size))


def addresses(indices: Iterable[int], size: int) -> list[str]:
    """`index_to_address` mapped over a cell-index list, order preserved — so a
    thermo path keeps bulb-first order and a cage's cells read row-major."""
    return [index_to_address(i, size) for i in indices]
