"""Synthesize the Schrödinger S-cell corpus links in code.

The `links/` corpus is built programmatically, never hand-authored on
SudokuMaker.com: each function here assembles a puzzle document and runs it
through `sudokumaker.document_to_link`, so a reviewer can read exactly what marking
case a fixture exercises and regenerate the whole set with `_corpus.synthesize()`.

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

from _corpus import authored_cage_style, blank_cells, boxed_document, jigsaw_document

from gridfind.sudokumaker import document_to_link

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


def _base_document(
    box_h: int,
    box_w: int,
    *,
    scell_cages: list[dict[str, object]],
    cells: list[dict[str, object]],
) -> dict[str, object]:
    """Wrap synthesized cells and S-cell marker cages into a SudokuMaker document."""
    return boxed_document(
        box_h,
        box_w,
        cells=cells,
        constraints=[
            {
                "name": "S-cell",
                "type": 2001,
                "cages": scell_cages,
                "style": authored_cage_style(),
            }
        ],
    )


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

    def give(self, index: int, value: int) -> _SchrodingerGrid:
        """Settle an ordinary cell to a plain given digit — a clue read directly
        off the board."""
        self.cells[index] = {"given": True, "value": value}
        return self

    def pencil(self, index: int, digits: set[int]) -> _SchrodingerGrid:
        """Pre-fill an ordinary cell's center marks: working state the solver
        narrows from, not a settled digit."""
        self.cells[index] = {"candidates": sum(1 << d for d in digits)}
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
        return document_to_link(
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
    """6x6 pin S-cell, `found` — one S-cell declared, the rest discovered, over
    the non-square (2x3) box shape. Two plain givens and two cells of center
    marks stand it up as a partial puzzle the solver advances from, rather than
    a blank board carrying a lone S-cell. Each clue matches the pattern
    solution, so a completion still exists (found); the marks name a superset of
    the solved digit, leaving the narrowing to the solver."""
    grid = _SchrodingerGrid(2, 3, discover_others=True)
    ordinary = [i for i in range(grid.size * grid.size) if i not in grid.scells]

    def solved(index: int) -> int:
        row, col = divmod(index, grid.size)
        return _solution_digit(row, col, grid.box_h, grid.box_w)

    grid.give(ordinary[0], solved(ordinary[0]))
    grid.give(ordinary[1], solved(ordinary[1]))
    for index in (ordinary[2], ordinary[3]):
        grid.pencil(index, {solved(index), solved(index) % grid.size + 1})
    return grid.link()


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


def malformed_out_of_domain() -> str:
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
    with_scell_block: bool = False,
) -> dict[str, object]:
    """A 4x4 jigsaw doubler document: `type 0` givens, `type 1` regions, a
    `Sum`-named `type 2001` killer block for the sum cages, and a named `Doubler`
    marker block that stands up the modifier directives. The sum rides a named
    `Sum` cage, so no live rule sits on an unnamed cosmetic block — the path
    the unnamed-cage warn-drop silences; a `Sum` label decodes to a killer cage the
    same as an unnamed block (ADR-0012). With `with_scell_block` a
    named-but-empty `S-cell` block rides along, enabling Schrödinger mode by
    presence (widening the domain to `0…N`, giving every cell `is_s` freedom to
    be discovered) without pinning any cell (ADR-0014)."""
    cells = blank_cells(4)
    for index, value in givens.items():
        cells[index] = {"given": True, "value": value}
    constraints: list[dict[str, object]] = [
        {
            "name": "Sum",
            "type": 2001,
            "cages": sum_cages,
            "style": authored_cage_style(),
        },
        {
            "name": "Doubler",
            "type": 2001,
            "cages": [{"cells": doubler_cells}],
            "style": authored_cage_style(),
        },
    ]
    if with_scell_block:
        constraints.append({"name": "S-cell", "type": 2001, "cages": []})
    return jigsaw_document(_DOUBLER_REGIONS, 4, cells=cells, constraints=constraints)


def found_doubler_4x4() -> str:
    """4x4 doubler, `found` — cells 9-11 (the rest of cell 8's row) given from
    a real completion, forcing cell 8 to 1 by ordinary row elimination alone,
    with no given on the cage cell (spec #723 dec 3); cell 12 stays
    undeclared but for its `Doubler` marker (never a `given`, so it never
    tripped the audit). Cage `{8, 12}` sums to 9 only because cell 12's
    digit counts double (`1 + 2·4`); without the doubler the cage is unsat."""
    return document_to_link(
        _doubler_document(
            sum_cages=[
                {"value": "9", "cells": [8, 12]},
                {"value": "11", "cells": [1, 2, 3]},
            ],
            givens={9: 3, 10: 2, 11: 4},
            doubler_cells=[12],
        )
    )


def found_doubled_scell_17cage_4x4() -> str:
    """4x4 doubler + Schrödinger, `found` — the doubled-S-cell motivating link.
    The killer cage `{R1C2, R1C3, R1C4} = 17` closes only if R1C3 is a *doubled
    S-cell* holding `{3, 4}`: `2·(3+4)` from the doubled pair, plus `2 + 1` from
    its two row partners, over the `0…4` domain the empty S-cell block widens
    to. Both channels must fire — the doubler alone caps two cells at
    `2·4 + 4 = 12`, the S-cell alone caps three digits at `4 + 3 + 2 = 9`."""
    return document_to_link(
        _doubler_document(
            sum_cages=[{"value": "17", "cells": [1, 2, 3]}],
            givens={},
            doubler_cells=[2, 12],
            with_scell_block=True,
        )
    )


def broke_doubler_4x4() -> str:
    """4x4 doubler, `broke` — cells 9-10 (two of cell 8's row partners) given
    from a real completion, narrowing cell 8 to the row's one remaining
    digit alongside cell 11's own sum-forced value, with no given on either
    cage cell (spec #723 dec 3; cell 11's value is still forced by its own
    singleton `group-sum`, never a given). The doubled cells over-constrain
    the sum cages past any completion, no matter which digit cell 8 lands
    on."""
    return document_to_link(
        _doubler_document(
            sum_cages=[{"value": "9", "cells": [8, 12]}, {"value": "2", "cells": [11]}],
            givens={9: 3, 10: 4},
            doubler_cells=[1, 12],
        )
    )


def found_cosmetic_cage_4x4() -> str:
    """4x4 jigsaw, `found` — a `Sum`-named cosmetic cage whose numeric `value`
    graduates it to a real killer sum (ADR-0008): cells `{0, 6}`, in different
    boxes and sharing no row/column, sum to 3 (`{1, 2}`). The board carries no
    other constraint, so the cage's no-repeats `cage` plus `group-sum` is the
    only rule beyond plain sudoku, and a completion exists (e.g. cell 0 = 1,
    cell 6 = 2). The mirror of `broke_cosmetic_cage_sumless_4x4`: a numeric
    value graduates the cage to a `group-sum`, where an empty one leaves only
    the bare no-repeats rule."""
    constraints: list[dict[str, object]] = [
        {
            "name": "Sum",
            "type": 2001,
            "cages": [{"value": "3", "cells": [0, 6]}],
            "style": authored_cage_style(),
        },
    ]
    return document_to_link(
        jigsaw_document(_DOUBLER_REGIONS, 4, constraints=constraints)
    )


def broke_cosmetic_cage_sumless_4x4() -> str:
    """4x4 jigsaw, `broke` — a `Sum`-named cosmetic cage with an empty value
    over two cells in different boxes. The empty value emits no `group-sum`, so
    the cage is a bare no-repeats rule; that rule alone makes the board
    unsatisfiable (drop the cage and it reads found). The cage is named `Sum`,
    not an unnamed cosmetic block, so its live no-repeats rule never rides the
    unnamed path the warn-drop silences; a `Sum` label decodes to a
    killer cage the same as an unnamed block (ADR-0012)."""
    cells = blank_cells(4)
    cells[1] = {"given": True, "value": 2}
    cells[7] = {"given": True, "value": 2}
    constraints: list[dict[str, object]] = [
        {
            "name": "Sum",
            "type": 2001,
            "cages": [{"value": "", "cells": [0, 6]}],
            "style": authored_cage_style(),
        },
    ]
    return document_to_link(
        jigsaw_document(_DOUBLER_REGIONS, 4, cells=cells, constraints=constraints)
    )


def found_cosmetic_cage_unrecognized_4x4() -> str:
    """4x4, `found` — proves nothing about the cage: the full grid of givens
    is the test. A fully-given classic solution (the same 2x2-box Latin grid
    `cli_test.py`'s `_classic_named_cage_link` uses) carries a `type 2001`
    cosmetic cage named `"Foobar"`, a name `naming._NAME_REGISTRY` doesn't
    answer for. The cage sits over cells `{0, 6}` (different boxes, rows, and
    columns), both holding solution digit 3: a `Sum`/`Killer`-named cage over
    the same cells would break immediately, since a killer cage forbids a
    repeated digit among its own cells (ADR-0012). Because `naming.classify`
    reports `"unrecognized"`, the cage is warn-dropped instead, so the
    verdict is computed from the given solution alone and reads found —
    proving the drop, not a coincidence, is what keeps it found."""
    solution = [3, 2, 4, 1, 4, 1, 3, 2, 2, 3, 1, 4, 1, 4, 2, 3]
    cells: list[dict[str, object]] = [{"given": True, "value": d} for d in solution]
    constraints: list[dict[str, object]] = [
        {
            "name": "Foobar",
            "type": 2001,
            "cages": [{"value": "6", "cells": [0, 6]}],
            "style": authored_cage_style(),
        },
    ]
    return document_to_link(
        jigsaw_document(_DOUBLER_REGIONS, 4, cells=cells, constraints=constraints)
    )


def found_cosmetic_cage_unnamed_4x4() -> str:
    """4x4, `found` — proves nothing about the cage: the full grid of givens
    is the test, same as `found_cosmetic_cage_unrecognized_4x4`. Carries the
    same fully-given solution, but a nameless `type 2001` cosmetic cage
    instead of a named one. `naming.classify` reports `"unnamed"` for an
    absent name, the other input the warn-drop
    (`cages.cosmetic_cage_constraints`) treats the same way as an
    unrecognized name: the block carries no rule, so the verdict is computed
    from the given solution alone."""
    solution = [3, 2, 4, 1, 4, 1, 3, 2, 2, 3, 1, 4, 1, 4, 2, 3]
    cells: list[dict[str, object]] = [{"given": True, "value": d} for d in solution]
    constraints: list[dict[str, object]] = [
        {
            "type": 2001,
            "cages": [{"value": "6", "cells": [0, 6]}],
            "style": authored_cage_style(),
        },
    ]
    return document_to_link(
        jigsaw_document(_DOUBLER_REGIONS, 4, cells=cells, constraints=constraints)
    )


def _broken_row_with_cosmetic_cage(cage_name: str | None) -> str:
    """4x4, `broke` — R1C1 and R1C2 both given digit 1, a plain row-uniqueness
    violation independent of any cage, carrying a `type 2001` cosmetic cage
    named `cage_name` (`None` for an unnamed block) over unrelated cells. The
    cage still warn-drops either way, so the break comes from the row repeat
    alone — proving the drop reaches the broke side too, not just found."""
    cells = blank_cells(4)
    cells[0] = {"given": True, "value": 1}
    cells[1] = {"given": True, "value": 1}
    block: dict[str, object] = {
        "type": 2001,
        "cages": [{"cells": [4, 8]}],
        "style": authored_cage_style(),
    }
    if cage_name is not None:
        block["name"] = cage_name
    return document_to_link(
        jigsaw_document(_DOUBLER_REGIONS, 4, cells=cells, constraints=[block])
    )


def broke_cosmetic_cage_unnamed_4x4() -> str:
    """4x4, `broke` — a row-repeat break (see `_broken_row_with_cosmetic_cage`)
    carrying a nameless cosmetic cage: the `"unnamed"` side of the coverage
    pair `found_cosmetic_cage_unnamed_4x4` starts."""
    return _broken_row_with_cosmetic_cage(None)


def broke_cosmetic_cage_unrecognized_4x4() -> str:
    """4x4, `broke` — a row-repeat break (see `_broken_row_with_cosmetic_cage`)
    carrying a cosmetic cage named `"Foobar"`: the `"unrecognized"` side of
    the coverage pair `found_cosmetic_cage_unrecognized_4x4` starts."""
    return _broken_row_with_cosmetic_cage("Foobar")


# The committed corpus: each `links/<name>.txt` is exactly `fn()` newline. The
# filename stem's first token is the e2e expected outcome (`found`/`broke`/
# `malformed`); the drift-guard test re-runs each `fn` and refuses a
# hand-edited file.
CORPUS: dict[str, Callable[[], str]] = {
    "found-scell-pin-4x4": found_pin,
    "found-scell-half-4x4": found_half,
    "found-scell-bare-4x4": found_bare,
    "found-scell-stray-marks-4x4": found_stray_marks,
    "found-schrodinger-6x6": found_schrodinger_6x6,
    "broke-scell-consistency-4x4": broke_consistency,
    "broke-schrodinger-4x4": broke_settled,
    "broke-scell-caged-value-4x4": broke_caged_value,
    "malformed-scell-out-of-domain-4x4": malformed_out_of_domain,
    "found-doubler-4x4": found_doubler_4x4,
    "found-doubled-scell-17cage-4x4": found_doubled_scell_17cage_4x4,
    "broke-doubler-4x4": broke_doubler_4x4,
    "broke-cosmetic-cage-sumless-4x4": broke_cosmetic_cage_sumless_4x4,
    "found-cosmetic-cage-4x4": found_cosmetic_cage_4x4,
    "found-cosmetic-cage-unrecognized-4x4": found_cosmetic_cage_unrecognized_4x4,
    "found-cosmetic-cage-unnamed-4x4": found_cosmetic_cage_unnamed_4x4,
    "broke-cosmetic-cage-unnamed-4x4": broke_cosmetic_cage_unnamed_4x4,
    "broke-cosmetic-cage-unrecognized-4x4": broke_cosmetic_cage_unrecognized_4x4,
}
