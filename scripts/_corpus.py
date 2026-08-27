"""The shared corpus-synthesis harness every `synthesize_*_links.py` script
builds on: the one `links/` directory, the one blank-cells/givens/box-or-
jigsaw-regions/`formatVersion` document builder, the one authored-cage style,
and the one write loop. Each synthesizer keeps only its own puzzle variant
(`CORPUS` and the constraints its fixtures need) and calls this harness
rather than hand-rolling a second copy — a fix to the write loop or the
document shape lands here once, not in every script. `synthesize()` is the
one driver that walks every module's `CORPUS` and regenerates it — run
`uv run python scripts/_corpus.py` to regenerate the whole corpus.

`iter_side_links` is the read-side counterpart: the one walk over
`links/*.txt` a corpus-wide audit script (`audit_link_coverage.py`,
`audit_givens_on_clue.py`) reads the committed corpus back through, rather
than each hand-rolling its own stem/side parse.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType

from gridfind.cell_geometry import row_col_to_index
from gridfind.layers.regions import box_regions

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"
_SCRIPTS_DIR = Path(__file__).resolve().parent

# The two verdict sides a corpus link declares through its filename prefix
# (the third, `malformed`, is a decode-error case with no verdict side, so
# it isn't one of these).
SIDES = ("found", "broke")


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


def grid_from_rows(rows: Sequence[Sequence[int]]) -> dict[tuple[int, int], int]:
    """A literal `rows[row-1][col-1]` completion — one row per source line —
    as the `(row, col) -> value` shape `off_path_givens` and `boxed_document`
    both take, so a line-family fixture spells its full-grid
    completion as short row tuples instead of one wide `(row, col): value`
    dict literal that would blow past the line-length limit at 9x9."""
    return {
        (row, col): value
        for row, cols in enumerate(rows, start=1)
        for col, value in enumerate(cols, start=1)
    }


def off_path_givens(
    grid: dict[tuple[int, int], int],
    path_cells: Sequence[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    """`grid` (a full, valid row/col/box-consistent completion) with
    `path_cells` withheld — the one shape every line-family fixture (spec
    #737) hands `boxed_document`'s `givens`. Every cell surrounding a tested
    line is given its `grid` value; the line's own cells are left for the
    solver to fill, forced to `grid`'s values by ordinary row/column/box
    elimination alone, so the line rule — not a given sitting on the line —
    is what decides the fixture's found/broke verdict."""
    path_set = set(path_cells)
    return {rc: value for rc, value in grid.items() if rc not in path_set}


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


def jigsaw_document(
    regions: Sequence[int],
    size: int,
    *,
    cells: list[dict[str, object]] | None = None,
    givens: dict[tuple[int, int], int] | None = None,
    constraints: Sequence[dict[str, object]] = (),
) -> dict[str, object]:
    """The jigsaw sibling of `boxed_document`: blank `size`x`size` cells (or a
    caller-built `cells`) with `givens` placed, wrapped with the classic
    `type 0`/`type 1` pair — but `regions` is a literal label array a fixture
    authors directly, not `box_regions`, for a puzzle whose regions aren't
    rectangles."""
    if cells is None:
        cells = blank_cells(size)
    if givens:
        place_givens(cells, size, givens)
    return wrap_document(
        cells,
        size,
        [{"type": 0}, {"type": 1, "regions": list(regions)}, *constraints],
    )


def authored_cage_style() -> dict[str, object]:
    """The default black cosmetic-cage style SudokuMaker writes for a
    hand-drawn named cage — outline and label both `#000000`. A synthesized
    cage block carries it so the emitted link is authentic: the cage renders
    with its cosmetic-cage icon the way a setter's own link would, rather
    than the style-less block SudokuMaker draws iconless. A fresh dict per
    call, so no two blocks alias one object. Display-only — `link_to_puzzle`
    never reads `style`."""
    return {"text": {"color": "#000000"}, "cage": {"color": "#000000"}}


def iter_side_links(links_dir: Path = LINKS_DIR) -> Iterator[tuple[str, str, str]]:
    """Every committed `found-`/`broke-` corpus link, in sorted filename
    order, as `(stem, side, link_text)`. Skips a `malformed-` link — a
    decode-error case, not verdict coverage — and warns to stderr on any
    other prefix, an unexpected corpus filename rather than one silently
    dropped from the walk (CODING_STANDARDS' fail-loud norm)."""
    for link_file in sorted(links_dir.glob("*.txt")):
        stem = link_file.stem
        side = stem.split("-", 1)[0]
        if side == "malformed":
            continue
        if side not in SIDES:
            print(
                f"skipping unexpected corpus filename: {link_file.name}",
                file=sys.stderr,
            )
            continue
        yield stem, side, link_file.read_text().strip()


def regenerate(corpus: dict[str, Callable[[], str]]) -> None:
    """Write every `name -> fn` pair in `corpus` to `links/<name>.txt` — the
    one write loop `synthesize` calls for each module's corpus."""
    for name, fn in corpus.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


def discover_modules() -> Iterator[ModuleType]:
    """Every `synthesize_*_links.py` module beside this file, imported in
    sorted filename order — the one module-discovery walk `synthesize` and
    `corpus_drift_test.py`'s parametrization both build on."""
    for path in sorted(_SCRIPTS_DIR.glob("synthesize_*_links.py")):
        yield importlib.import_module(path.stem)


def synthesize() -> None:
    """Regenerate every synthesizer's corpus: walks each `synthesize_*_links.py`
    module's `CORPUS` through `regenerate` — the one driver that replaces
    every script's own repeated `main`/docstring plumbing."""
    for module in discover_modules():
        regenerate(module.CORPUS)


def synthesizer_by_stem() -> dict[str, Callable[[], str]]:
    """Every `CORPUS` entry across every `synthesize_*_links.py` module,
    merged into one `stem -> synthesizer` dict — the same discovery walk
    `synthesize`/`corpus_drift_test.py` build on, reused so a stem's
    synthesizer (and its docstring) can be looked up without a second module
    scan. A stem absent here is a legacy link no synthesizer built."""
    return {
        name: fn for module in discover_modules() for name, fn in module.CORPUS.items()
    }


if __name__ == "__main__":
    synthesize()
