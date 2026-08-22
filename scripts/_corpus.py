"""The shared corpus-synthesis harness every `synthesize_*_links.py` script
builds on: the one `links/` directory, the one blank-cells/givens/box-regions/
`formatVersion` document builder, and the one write loop. Each synthesizer
keeps only its own puzzle variant (`CORPUS` and the constraints its fixtures
need) and calls this harness rather than hand-rolling a second copy — a fix
to the write loop or the document shape lands here once, not in every script.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from gridfind.cell_geometry import row_col_to_index
from gridfind.layers.regions import box_regions

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"


def blank_cells(size: int) -> list[dict[str, object]]:
    """`size*size` empty cell dicts, row-major — every synthesizer's starting
    grid before givens (or other per-cell state) are placed."""
    return [{} for _ in range(size * size)]


def place_givens(
    cells: list[dict[str, object]],
    size: int,
    givens: dict[tuple[int, int], int],
) -> None:
    """Mutate `cells` in place, setting each 1-based `(row, col)` -> `value`
    given as `{"given": True, "value": value}` at its row-major index."""
    for (row, col), value in givens.items():
        cells[row_col_to_index(row, col, size)] = {"given": True, "value": value}


def wrap_document(
    cells: list[dict[str, object]],
    size: int,
    constraints: Sequence[dict[str, object]],
) -> dict[str, object]:
    """The outermost shape every synthesized document shares: `cells` and
    `constraints` under a `size`x`size` `puzzle`, inside `formatVersion` —
    with no assumption about how `constraints` derives its regions, so a
    jigsaw fixture (a literal region array, not `box_regions`) wraps through
    this the same as a boxed one."""
    return {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": cells, "size": size, "constraints": list(constraints)},
    }


def boxed_document(
    box_h: int,
    box_w: int,
    *,
    cells: list[dict[str, object]] | None = None,
    givens: dict[tuple[int, int], int] | None = None,
    constraints: Sequence[dict[str, object]] = (),
) -> dict[str, object]:
    """A `box_h`x`box_w`-boxed SudokuMaker document: blank `box_h*box_w`
    square cells (or a caller-built `cells`, for a fixture whose per-cell
    state is more than plain givens) with `givens` placed, wrapped with the
    classic `type 0`/`type 1` (box regions) pair and any extra `constraints`
    appended after."""
    size = box_h * box_w
    if cells is None:
        cells = blank_cells(size)
    if givens:
        place_givens(cells, size, givens)
    region_numbers = box_regions(size, box_h, box_w).to_labels(size)
    return wrap_document(
        cells,
        size,
        [{"type": 0}, {"type": 1, "regions": region_numbers}, *constraints],
    )


def regenerate(corpus: dict[str, Callable[[], str]]) -> None:
    """Write every `name -> fn` pair in `corpus` to `links/<name>.txt` — the
    one write loop each synthesizer's `main()` calls."""
    for name, fn in corpus.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")
