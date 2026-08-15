"""`decode_link`: thread every module's decode piece into one `Puzzle` +
`WorkingState`.

The decode is split by responsibility across the package's other modules —
`boundary` (document decompress/compress, size/domain, the shared
enabled-block walk), `cells` (per-cell decode), `cages` (killer/cosmetic
cages, thermometers), `markers` (named marker-cage classification, ADR-0012),
`edge_clues` (XV/kropki), `regions` (the `type 1` block), and `registry`
(`DECODER_REGISTRY`) — with `decode_link` here as the one function that
threads all of them together.
"""

from __future__ import annotations

from typing import Any

from gridfind.cell_geometry import cell_geometry
from gridfind.puzzle import Board, Constraint, Puzzle, WorkingState
from gridfind.sudokumaker.boundary import (
    _board_size,
    _digit_domain,
    _schrodinger_domain,
    decode_document,
)
from gridfind.sudokumaker.cages import _cosmetic_cage_constraints
from gridfind.sudokumaker.cells import _CellDecode, _decode_cell
from gridfind.sudokumaker.markers import (
    _COSMETIC_CAGE_TYPE,
    _has_scell_marker_block,
    _scell_marker_values,
)
from gridfind.sudokumaker.registry import DECODER_REGISTRY, _warn_on_dropped_constraints


def decode_link(
    link: str,
    *,
    ignore_unknown_named_cages: bool = False,
) -> tuple[Puzzle, WorkingState]:
    """Map a SudokuMaker `?puzzle=` link (or a bare payload) to a square-N
    `Puzzle` + `WorkingState`, sizing the board and domain from the link
    itself. Raises `ValueError` on a link gridfind can't answer.

    Doublers and S-cells are **inferred from the link's named marker cages**,
    never declared out of band — a `type 2001` cosmetic-cage block whose
    top-level `name` reads as a marker stands up its variant on its own, and a
    single link may carry both a `Doubler` and an `S-cell` block at once.

    A `type 2001` cosmetic-cage block whose top-level `name` names a
    recognized real-cage label (`Sum`/`Killer`, case-insensitive and trimmed)
    decodes as an ordinary killer cage with the name discarded; any other name
    raises `ValueError` unless `ignore_unknown_named_cages` downgrades that
    refusal to strip-and-honor (ADR-0012).

    A `type 2001` block named `Doubler` (case-insensitive, trimmed) marks every
    cell it contains a declared doubler — one `ModifierDirective` per cell, no
    `cage`/`group-sum` for that block — and stands up the `doubler` constraint.
    The marker is orthogonal to the cell's digit: a doubler holds one digit
    worth twice its value, so a given or placement on a marked cell still lands.

    A `type 2001` block named `S-cell`/`Schrödinger` is the analogous S-cell
    marker: each contained cell is a declared S-cell reading its marker cage's
    own `value` for the pair/half/bare directive (ADR-0014) — a comma-split
    `"a,b"` or the two-digit scalar shorthand in a single-digit domain pins the
    pair, one digit is a half S-cell, absent/empty/unparseable is a bare
    S-cell. No `cage`/`group-sum` is emitted for that block. A settled value on
    a marked cell (the cell's own `value`, distinct from the cage's) decodes
    alongside the marker's directive rather than being refused — the two
    collide at solve time (ADR-0014). The marker widens the domain by
    the classic `k = 1` extra digit (`range(minDigit, minDigit + size + 1)`),
    relaxes the classic-only guard, and synthesizes the `schrodinger`
    constraint. Once that layer exists, every cell's settled `given`/bare
    `value` placement — marked or not — decodes to a **singleton pin**
    (`is_s == 0`), not a plain given/placement: the wire's `given` flag does
    not affect the S-cell reading (ADR-0014)."""
    puzzle_data: Any = decode_document(link)["puzzle"]
    size = _board_size(puzzle_data)
    _warn_on_dropped_constraints(puzzle_data)

    cells = puzzle_data["cells"]
    # A named `S-cell`/`Schrödinger` block splits into two signals. Its
    # *presence* enables the mode — widening the domain and synthesizing the
    # `schrodinger` constraint that gives every cell the `is_s` freedom the
    # solver discovers S-cells with — even when the block names no cells
    # (ADR-0014). Its *membership* pins known S-cells: each named address maps
    # to its marker cage's own `value`, the pair/half/bare source (ADR-0014)
    # the S-cell branch of the per-cell decode reads.
    scell_values = _scell_marker_values(puzzle_data, size)
    is_schrodinger = _has_scell_marker_block(puzzle_data)
    domain = (
        _schrodinger_domain(puzzle_data, size)
        if is_schrodinger
        else _digit_domain(puzzle_data, size)
    )
    # `sudokumaker` has no engine, so it builds its own descriptor straight
    # from the board it holds rather than re-deriving the `RxCy` address grid
    # by hand (ADR-0004). `cells` is SudokuMaker's own row-major layout, the
    # same order `geometry.grid` flattens to, so zipping the two walks both
    # in lockstep without either side recomputing the other's indexing.
    board = Board(size=size, values=domain)
    geometry = cell_geometry(board)
    addresses = [address for row in geometry.grid for address in row]
    per_cell: list[_CellDecode] = []
    for cell, address in zip(cells, addresses, strict=True):
        per_cell.append(
            _decode_cell(
                cell,
                address,
                domain,
                is_schrodinger=is_schrodinger,
                is_scell_marker=address in scell_values,
                scell_value=scell_values.get(address),
            )
        )
    decoded = _CellDecode.concat(per_cell)

    # SudokuMaker leaves rows/cols implicit under `type 0`; gridfind makes both
    # explicit — rows/cols always bare, everything else via DECODER_REGISTRY.
    # The cosmetic-cage type alone takes a decode_link-scoped extra argument
    # (the ignore flag) and returns modifier directives alongside its
    # constraints, so it is dispatched by hand rather than through the
    # registry's generic two-argument, constraints-only call.
    constraints = [Constraint("rows-distinct"), Constraint("cols-distinct")]
    cosmetic_cage_decode = _cosmetic_cage_constraints(
        puzzle_data, size, ignore_unknown_named_cages=ignore_unknown_named_cages
    )
    constraints.extend(cosmetic_cage_decode.constraints)
    for kind, decoded_type in DECODER_REGISTRY.items():
        if kind == _COSMETIC_CAGE_TYPE or decoded_type.handler is None:
            continue
        constraints.extend(decoded_type.handler(puzzle_data, size))
    if is_schrodinger:
        constraints.append(Constraint("schrodinger"))
    if cosmetic_cage_decode.modifier_directives:
        constraints.append(Constraint("doubler"))

    puzzle = Puzzle(board=board, constraints=tuple(constraints), givens=decoded.givens)
    state = WorkingState(
        places=decoded.places,
        candidates=decoded.candidates,
        s_directives=decoded.s_directives,
        modifier_directives=cosmetic_cage_decode.modifier_directives,
    )
    return puzzle, state
