"""Synthesize the Schrödinger S-cell corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.encode_link`, so a reviewer can read exactly what marking
case a fixture exercises and regenerate the whole set with `main()`.

Every S-cell link declares its variant through a named `type 2001` marker cage
(`name: "S-cell"`), the sole decode-time S-cell channel (CONTEXT.md
`schrodinger`, ADR-0012). A cell's directive rides the marker cage's own
`value`: a comma-split `"a,b"` pins the pair, one digit is a half S-cell, an
absent value is a bare S-cell. Doublers ride a `name: "Doubler"` marker cage
over a sum-cage cell, where the doubled value is load-bearing.

The construction is the classic "pattern" sudoku: a Latin square that respects
boxes, with one cell per row/column/box promoted to an S-cell on a transversal
so every line holds all `N + 1` digits once. The ordinary cells stay blank, so
the solver reconstructs the grid rather than reading back an answer key.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gridfind.sudokumaker import encode_link

LINKS_DIR = Path(__file__).resolve().parent.parent / "src" / "gridfind" / "links"

# The classic extra digit the Schrödinger layer widens the domain by (k = 1);
# 0 sits below every ordinary given (which use 1..N), so an S-cell pinned
# `{0, base}` supplies the tenth digit its row/column/box would otherwise lack.
_EXTRA = 0


def _solution_digit(row: int, col: int, box_h: int, box_w: int) -> int:
    """The filled-square digit at `(row, col)` for a `box_h`x`box_w`-box board,
    in `1..N`. The standard pattern construction: a row shift by the band index
    keeps boxes distinct while rows and columns stay permutations."""
    size = box_h * box_w
    return (box_w * (row % box_h) + row // box_h + col) % size + 1


def _transversal(size: int, box_h: int, box_w: int) -> dict[int, int]:
    """One cell per row that also lands one per column and one per box — the S-cell
    positions. Maps each such cell index to its solution digit. `col = (row*box_w
    + row//box_h) % N` walks a diagonal that visits every column once and every
    box once for any box shape."""
    positions: dict[int, int] = {}
    for row in range(size):
        col = (row * box_w + row // box_h) % size
        positions[row * size + col] = _solution_digit(row, col, box_h, box_w)
    return positions


def _regions(size: int, box_h: int, box_w: int) -> list[int]:
    """The `type 1` region id per cell: which box each cell belongs to, so the
    board carries its box-distinct constraint explicitly."""
    boxes_per_row = size // box_w
    return [
        (row // box_h) * boxes_per_row + col // box_w
        for row in range(size)
        for col in range(size)
    ]


def _base_document(
    box_h: int,
    box_w: int,
    *,
    scell_cages: list[dict[str, object]],
    cells: list[dict[str, object]],
) -> dict[str, object]:
    """Wrap synthesized cells and S-cell marker cages into a SudokuMaker document."""
    size = box_h * box_w
    puzzle = {
        "cells": cells,
        "size": size,
        "minDigit": _EXTRA,
        "constraints": [
            {"type": 0},
            {"type": 1, "regions": _regions(size, box_h, box_w)},
            {"name": "S-cell", "type": 2001, "cages": scell_cages},
        ],
    }
    return {"formatVersion": "1.5.0", "puzzle": puzzle}


class _SchrodingerGrid:
    """A classic Schrödinger puzzle under construction: ordinary cells left
    blank for the solver, the *first* S-cell (lowest cell index) marked and
    pinned `{0, base}` through its marker cage. What happens to the other
    transversal positions is the `discover_others` switch:

    - `False` — they are pinned as S-cells too, through their own `{0, base}`
      cages. A broke case mutates the first cell and wants the rest fixed, so
      the break it introduces is the sole cause.
    - `True` — they are left empty for the solver to discover as S-cells. A real
      found puzzle that declares one S-cell and solves for the rest, rather than
      handing over a board where every S-cell is already specified."""

    def __init__(
        self, box_h: int, box_w: int, *, discover_others: bool = False
    ) -> None:
        self.box_h = box_h
        self.box_w = box_w
        self.size = box_h * box_w
        self.scells = _transversal(self.size, box_h, box_w)
        self.first = min(self.scells)
        self.cells: list[dict[str, object]] = []
        self.cages: list[dict[str, object]] = []
        for index in range(self.size * self.size):
            if index == self.first or (index in self.scells and not discover_others):
                self.cells.append({})
                self.cages.append(
                    {"value": f"{_EXTRA},{self.scells[index]}", "cells": [index]}
                )
            else:
                # An ordinary cell, left blank for the solver: pinning the whole
                # Latin square would hand over an answer key, not a puzzle. A
                # discovered S-cell (index in self.scells) reaches here too and
                # is likewise left blank for the solver to find.
                self.cells.append({})

    def _first_cage(self) -> dict[str, object]:
        return next(c for c in self.cages if c["cells"] == [self.first])

    def set_first_value(self, value: str | None) -> _SchrodingerGrid:
        """Override the first S-cell's marker-cage `value` (its directive
        source). `None` drops the key, declaring a bare S-cell."""
        cage = self._first_cage()
        if value is None:
            cage.pop("value", None)
        else:
            cage["value"] = value
        return self

    def set_first_marks(self, digits: set[int]) -> _SchrodingerGrid:
        """Set the first S-cell's own center marks — the consistency layer over
        its cage directive."""
        self.cells[self.first] = {"candidates": sum(1 << d for d in digits)}
        return self

    def give_first_own_value(self, digit: int) -> _SchrodingerGrid:
        """Settle the first S-cell's own large digit alongside its marker cage.
        The cage's directive and the cell's own singleton pin collide on
        S-cell-ness (CONTEXT.md `schrodinger`)."""
        self.cells[self.first] = {"given": True, "value": digit}
        return self

    def uncage_first_as_given(self) -> _SchrodingerGrid:
        """Drop the first S-cell's marker cage and settle it as a plain given of
        its base digit. Its row/column/box then has no S-cell to supply the
        extra `0`, so the board is unsatisfiable."""
        self.cages = [c for c in self.cages if c["cells"] != [self.first]]
        row, col = divmod(self.first, self.size)
        self.cells[self.first] = {
            "given": True,
            "value": _solution_digit(row, col, self.box_h, self.box_w),
        }
        return self

    def link(self) -> str:
        return encode_link(
            _base_document(
                self.box_h, self.box_w, scell_cages=self.cages, cells=self.cells
            )
        )


def found_pin() -> str:
    """4x4 pin S-cell, `found` — one S-cell declared with a comma pair `{0, base}`
    cage, the other three discovered by the solver."""
    return _SchrodingerGrid(2, 2, discover_others=True).link()


def found_half() -> str:
    """4x4 half S-cell, `found` — the marked cage names one digit of its pair; the
    solver fills the partner and finds the other three S-cells."""
    grid = _SchrodingerGrid(2, 2, discover_others=True)
    return grid.set_first_value(str(_EXTRA)).link()


def found_bare() -> str:
    """4x4 bare S-cell, `found` — the marked cage carries no value; the solver
    finds both its pair and the other three S-cells."""
    return _SchrodingerGrid(2, 2, discover_others=True).set_first_value(None).link()


def found_stray_marks() -> str:
    """4x4 pin S-cell with superset center marks, `found` — marks that contain the
    pinned pair (and extras) satisfy the consistency restriction."""
    grid = _SchrodingerGrid(2, 2, discover_others=True)
    pair = {_EXTRA, grid.scells[grid.first]}
    return grid.set_first_marks(pair | set(range(1, grid.size + 1))).link()


def found_schrodinger_6x6() -> str:
    """6x6 pin S-cell, `found` — one S-cell declared, the rest discovered, over the
    non-square (2x3) box shape."""
    return _SchrodingerGrid(2, 3, discover_others=True).link()


def broke_consistency() -> str:
    """4x4 pin S-cell with center marks that omit a pinned digit, `broke` — the
    restriction can't hold the pair, so the model is infeasible."""
    grid = _SchrodingerGrid(2, 2)
    base = grid.scells[grid.first]
    return grid.set_first_marks({base}).link()  # omits the extra 0 of the pair


def broke_settled() -> str:
    """4x4 Schrödinger, `broke` — one S-cell position is settled as a plain
    given, leaving the extra `0` unplaceable in its row/column/box."""
    return _SchrodingerGrid(2, 2).uncage_first_as_given().link()


def broke_caged_value() -> str:
    """4x4 S-cell that also carries its own settled digit, `broke` — the cage's
    pin and the cell's singleton pin collide on S-cell-ness."""
    grid = _SchrodingerGrid(2, 2)
    return grid.give_first_own_value(grid.scells[grid.first]).link()


def invalid_out_of_domain() -> str:
    """4x4 S-cell whose cage `value` names a digit off the board — a malformed
    directive the front door refuses with exit 2, not a `broke` verdict."""
    return _SchrodingerGrid(2, 2).set_first_value(f"{_EXTRA},99").link()


# A doubler fixture is a 4x4 jigsaw puzzle with a named `Doubler` marker cage
# over a cell in a sum cage, where the doubled value is load-bearing: the cage
# sum only closes because that cell's digit counts twice.
_DOUBLER_REGIONS = [0, 0, 1, 1, 0, 0, 1, 1, 2, 2, 3, 3, 2, 2, 3, 3]


def _doubler_document(
    *,
    sum_cages: list[dict[str, object]],
    givens: dict[int, int],
    doubler_cells: list[int],
) -> dict[str, object]:
    """A 4x4 jigsaw doubler document: `type 0` givens, `type 1` regions, an
    unnamed `type 2001` killer block for the sum cages, and a named `Doubler`
    marker block that stands up the modifier directives."""
    cells: list[dict[str, object]] = [{} for _ in range(16)]
    for index, value in givens.items():
        cells[index] = {"given": True, "value": value}
    puzzle = {
        "cells": cells,
        "size": 4,
        "constraints": [
            {"type": 0},
            {"type": 1, "regions": _DOUBLER_REGIONS},
            {"type": 2001, "cages": sum_cages},
            {"name": "Doubler", "type": 2001, "cages": [{"cells": doubler_cells}]},
        ],
    }
    return {"formatVersion": "1.5.0", "puzzle": puzzle}


def found_doubler_4x4() -> str:
    """4x4 doubler, `found` — cage `{8, 12}` sums to 9 only because cell 12's
    digit counts double (`1 + 2·4`); without the doubler the cage is unsat."""
    return encode_link(
        _doubler_document(
            sum_cages=[
                {"value": "9", "cells": [8, 12]},
                {"value": "11", "cells": [1, 2, 3]},
            ],
            givens={8: 1},
            doubler_cells=[12],
        )
    )


def broke_doubler_4x4() -> str:
    """4x4 doubler, `broke` — the doubled cells over-constrain the sum cages past
    any completion."""
    return encode_link(
        _doubler_document(
            sum_cages=[{"value": "9", "cells": [8, 12]}, {"value": "2", "cells": [11]}],
            givens={8: 1},
            doubler_cells=[1, 12],
        )
    )


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e verdict (`found`/`broke`/`invalid`);
# the drift-guard test re-runs each `fn` and refuses a hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-scell-pin-4x4": found_pin,
    "found-scell-half-4x4": found_half,
    "found-scell-bare-4x4": found_bare,
    "found-scell-stray-marks-4x4": found_stray_marks,
    "found-schrodinger-6x6": found_schrodinger_6x6,
    "broke-scell-consistency-4x4": broke_consistency,
    "broke-schrodinger-4x4": broke_settled,
    "broke-scell-caged-value-4x4": broke_caged_value,
    "invalid-scell-out-of-domain-4x4": invalid_out_of_domain,
    "found-doubler-4x4": found_doubler_4x4,
    "broke-doubler-4x4": broke_doubler_4x4,
}


def main() -> None:
    """Regenerate every corpus file from its synthesizer."""
    for name, fn in CORPUS.items():
        (LINKS_DIR / f"{name}.txt").write_text(fn() + "\n")
        print(f"wrote {name}.txt")


if __name__ == "__main__":
    main()
