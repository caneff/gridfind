"""`decode_link`: thread every module's decode piece into one `Puzzle` +
`WorkingState`.

The decode is split by responsibility across the package's other modules —
`boundary` (document decompress/compress, size/domain, the shared
enabled-block walk), `cells` (per-cell decode), `cages` (killer/cosmetic
cages, thermometers), `markers` (named marker-cage classification, ADR-0012),
`global_flags` (the payload-less `Somedoku` component, spec #431/#436),
`edge_clues` (XV/kropki), `regions` (the `type 1` block), and `registry`
(`DECODER_REGISTRY`) — with `decode_link` here as the one function that
threads all of them together.
"""

from __future__ import annotations

from typing import Any

from gridfind.cell_geometry import cell_geometry
from gridfind.puzzle import Board, Constraint, Puzzle, WorkingState
from gridfind.sudokumaker.boundary import (
    board_size,
    bucket_constraints_by_type,
    decode_document,
    digit_domain,
    schrodinger_domain,
)
from gridfind.sudokumaker.cages import cosmetic_cage_constraints
from gridfind.sudokumaker.cells import CellDecode, decode_cell
from gridfind.sudokumaker.global_flags import has_somedoku_component
from gridfind.sudokumaker.markers import has_scell_marker_block, scell_marker_values
from gridfind.sudokumaker.registry import DECODER_REGISTRY, warn_on_dropped_constraints


def decode_link(link: str) -> tuple[Puzzle, WorkingState]:
    """Map a SudokuMaker `?puzzle=` link (or a bare payload) to a square-N
    `Puzzle` + `WorkingState`, sizing the board and domain from the link
    itself. Raises `ValueError` on a link gridfind can't answer, and
    `MalformedPuzzleError` on the narrower case of a modifier marker cage
    declaring conflicting facts about a puzzle-wide value (ADR-0016 decisions
    3-4, detailed in `cosmetic_cage_constraints`'s own docstring).

    Doublers, constant modifiers, and S-cells are **inferred from the link's
    named marker cages**, never declared out of band — a `type 2001`
    cosmetic-cage block whose top-level `name` reads as a marker stands up its
    variant on its own, and a single link may carry both a modifier marker
    block and an `S-cell` block at once (though not both a `Doubler` and a
    `Constant`/`Nullifier` block — one modifier type per puzzle).

    A `type 2001` cosmetic-cage block whose top-level `name` names a
    recognized real-cage label (`Sum`/`Killer`, case-insensitive and trimmed)
    decodes as an ordinary killer cage with the name discarded. An unnamed
    block, or one whose name gridfind does not recognize, carries no rule: a
    non-empty one is dropped with a loud stderr warning naming the block
    (ADR-0012).

    A `type 2001` block named `Doubler` (case-insensitive, trimmed) marks every
    cell it contains a declared doubler — one `ModifierDirective` per cell, no
    `cage`/`group-sum` for that block — and stands up the `doubler` constraint.
    The marker is orthogonal to the cell's digit: a doubler holds one digit
    worth twice its value, so a given or placement on a marked cell still lands.
    A block named `Constant <N>`/`Nullifier` is the analogous constant-modifier
    marker: the same per-cell `ModifierDirective`s, but the synthesized
    constraint is `constant` carrying `k` read from the name (`Nullifier` is
    the `k = 0` spelling) rather than a fixed `doubler` (ADR-0016).

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
    not affect the S-cell reading (ADR-0014).

    A `type 1000` custom constraint or a `type 2001` cosmetic cage named
    `Somedoku` (case-insensitive, trimmed, either carrier — spec #431/#436)
    is a **global flag**: its cells and value, whichever carrier's payload
    it rides, are ignored entirely, and its bare presence stands up the
    `line-count-distinct` constraint in place of the classic
    `rows-distinct`/`cols-distinct`/`regions-distinct` triplet — a somedoku
    grid runs on its own row-*n*/col-*n* distinct-count rule alone, no boxes
    and no classic uniqueness, which a row or column short of size `N`
    could never satisfy alongside `line-count-distinct` at once. A disabled
    `Somedoku` block, on either carrier, contributes nothing and the classic
    triplet decodes as usual."""
    puzzle_data: Any = decode_document(link)["puzzle"]
    size = board_size(puzzle_data)
    warn_on_dropped_constraints(puzzle_data)
    # One pass over puzzle_data["constraints"], grouped by wire `type`, so every
    # per-type decoder below selects its own type's blocks by one dict lookup
    # (via `enabled_blocks`).
    buckets = bucket_constraints_by_type(puzzle_data)
    is_somedoku = has_somedoku_component(buckets)

    cells = puzzle_data["cells"]
    # A named `S-cell`/`Schrödinger` block splits into two signals. Its
    # *presence* enables the mode — widening the domain and synthesizing the
    # `schrodinger` constraint that gives every cell the `is_s` freedom the
    # solver discovers S-cells with — even when the block names no cells
    # (ADR-0014). Its *membership* pins known S-cells: each named address maps
    # to its marker cage's own `value`, the pair/half/bare source (ADR-0014)
    # the S-cell branch of the per-cell decode reads.
    scell_values = scell_marker_values(buckets, size)
    is_schrodinger = has_scell_marker_block(buckets)
    domain = (
        schrodinger_domain(puzzle_data, size)
        if is_schrodinger
        else digit_domain(puzzle_data, size)
    )
    # `sudokumaker` has no engine, so it builds its own descriptor straight
    # from the board it holds rather than re-deriving the `RxCy` address grid
    # by hand (ADR-0004). `cells` is SudokuMaker's own row-major layout, the
    # same order `geometry.grid` flattens to, so zipping the two walks both
    # in lockstep without either side recomputing the other's indexing.
    board = Board(size=size, values=domain)
    geometry = cell_geometry(board)
    addresses = [address for row in geometry.grid for address in row]
    per_cell: list[CellDecode] = []
    for cell, address in zip(cells, addresses, strict=True):
        per_cell.append(
            decode_cell(
                cell,
                address,
                domain,
                is_schrodinger=is_schrodinger,
                is_scell_marker=address in scell_values,
                scell_value=scell_values.get(address),
            )
        )
    decoded = CellDecode.concat(per_cell)

    # SudokuMaker leaves rows/cols implicit under `type 0`; gridfind makes both
    # explicit — rows/cols always bare, everything else via DECODER_REGISTRY.
    # A somedoku puzzle runs on `line-count-distinct` alone in their place
    # (classic uniqueness is incompatible with a distinct-count target below
    # `N`), and skips `type 1`'s regions/box rule the same way — a somedoku
    # grid carries no boxes.
    # The cosmetic-cage type alone returns modifier directives alongside its
    # constraints, so it is dispatched by hand rather than through the
    # registry's generic two-argument, constraints-only call.
    constraints = (
        [Constraint("line-count-distinct")]
        if is_somedoku
        else [Constraint("rows-distinct"), Constraint("cols-distinct")]
    )
    cosmetic_cage_decode = cosmetic_cage_constraints(buckets, size)
    constraints.extend(cosmetic_cage_decode.constraints)
    for wire_type, decoded_type in DECODER_REGISTRY.items():
        if decoded_type.handler is None:
            continue
        if is_somedoku and wire_type == 1:
            continue
        constraints.extend(decoded_type.handler(buckets, size))
    if is_schrodinger:
        constraints.append(Constraint("schrodinger"))
    if cosmetic_cage_decode.modifier_constraint is not None:
        constraints.append(cosmetic_cage_decode.modifier_constraint)

    puzzle = Puzzle(board=board, constraints=tuple(constraints), givens=decoded.givens)
    state = WorkingState(
        places=decoded.places,
        candidates=decoded.candidates,
        s_directives=decoded.s_directives,
        modifier_directives=cosmetic_cage_decode.modifier_directives,
    )
    return puzzle, state
