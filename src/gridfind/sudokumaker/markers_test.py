"""`markers`: the named cosmetic cages that declare a puzzle feature rather than
a constraint — `Doubler`, `Constant <N>` / `Nullifier`, and `S-cell` — plus the
classifier and the display colorizer.

`cosmetic_cage_kind` is the one home that reads a cage's name into its kind
(unnamed / killer / rellik / doubler / s-cell / constant / unrecognized,
ADR-0012, ADR-0018). A
`Doubler` or `Constant` cage emits modifier directives; an `S-cell` cage
declares S-cells, infers Schrödinger-ness
from its mere presence, and sources each cell's pin/half/bare directive from its
own `value` (ADR-0014). `colorize_marker_cages` writes the cosmetic display
color a re-emitted link needs, reading `_MARKER_COLOR_PALETTE` from beside it.
"""

import json
from typing import Any, cast

import pytest

from gridfind.engine import MalformedPuzzleError
from gridfind.puzzle import Board, Constraint, Given, ModifierDirective
from gridfind.s_directives import (
    BareSCell,
    HalfSCell,
    SCellMarkRestriction,
    SCellPin,
    SDirective,
    SingletonPin,
)
from gridfind.sudokumaker import (
    colorize_marker_cages,
    cosmetic_cage_kind,
    document_to_link,
    link_to_puzzle,
)
from gridfind.sudokumaker.conftest import (
    EMPTY_CELLS,
    JIGSAW_REGIONS,
    STANDARD_REGIONS,
    WIRE_CONSTRAINTS,
    encode_document,
    mask,
)
from gridfind.sudokumaker.markers import _MARKER_COLOR_PALETTE, MARKER_LABELS
from gridfind.verdict import verdict

# A Schrödinger link's own cosmetic vocabulary: unknown types the decoder must
# ignore (not reject) once a marker makes the link Schrödinger, plus a disabled
# duplicate of the classic type-1 regions matrix, which must lose to the
# enabled one.
_SCHRODINGER_WIRE_CONSTRAINTS = [
    {"type": 0},
    {"type": 1, "regions": STANDARD_REGIONS},
    {"type": 1, "regions": JIGSAW_REGIONS, "disabled": True},
    {"type": 2003},
    {"type": 303, "disabled": True},
]

_S_CELL_MARKER = {"name": "S-cell", "type": 2001, "cages": [{"cells": [0]}]}


def _schrodinger_link(cells: list[dict[str, object]], *, min_digit: int = 0) -> str:
    """A synthesised Schrödinger link: an `S-cell` marker cage (which infers
    Schrödinger-ness), `minDigit`, and the cosmetic constraint mix a real link
    carries alongside a caller-supplied `cells` array."""
    return encode_document(
        {
            "cells": cells,
            "minDigit": min_digit,
            "constraints": [*_SCHRODINGER_WIRE_CONSTRAINTS, _S_CELL_MARKER],
        }
    )


def _s_cell_cage_link(
    value: object, *, min_digit: int = 0, marks: set[int] | None = None
) -> str:
    """A single-cell `S-cell` marker cage over R1C1, carrying `value` (omitted
    entirely when `None`) — the cage-value pair-source fixture (ADR-0014).
    `marks` optionally sets the cell's own center marks, present to show the
    cage `value` alone picks the directive and stray marks are ignored."""
    cage: dict[str, object] = {"cells": [0]}
    if value is not None:
        cage["value"] = value
    cells = list(EMPTY_CELLS)
    if marks:
        cells[0] = {"candidates": mask(marks)}
    return encode_document(
        {
            "cells": cells,
            "minDigit": min_digit,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "S-cell", "type": 2001, "cages": [cage]},
            ],
        }
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (None, "unnamed"),
        ("", "unnamed"),
        ("   ", "unnamed"),
        ("Sum", "killer"),
        ("Killer", "killer"),
        ("Rellik", "rellik"),
        ("Anti", "rellik"),
        ("Doubler", "doubler"),
        ("  doubler ", "doubler"),
        ("S-cell", "s-cell"),
        ("Schrödinger", "s-cell"),
        ("Nullifier", "constant"),
        ("Constant 5", "constant"),
        ("Constant -3", "constant"),
        ("Constant", "unrecognized"),
        ("Constant xyz", "unrecognized"),
        ("Somedoku", "somedoku"),
        ("  somedoku ", "somedoku"),
        ("Whimsy", "unrecognized"),
    ],
    ids=[
        "none",
        "empty",
        "blank",
        "sum-label",
        "killer-label",
        "rellik-label",
        "anti-label",
        "doubler",
        "doubler-padded",
        "s-cell",
        "schrodinger",
        "nullifier",
        "constant-n",
        "constant-negative",
        "bare-constant",
        "constant-non-numeric",
        "somedoku",
        "somedoku-padded-lower",
        "unknown",
    ],
)
def test_cosmetic_cage_kind_classifies_the_name(name: object, expected: str) -> None:
    # The public seven-way classifier is the one home every named-cosmetic-cage
    # read routes through (ADR-0012, extended by ADR-0016):
    # unnamed, killer cage, Doubler marker, S-cell marker, Constant/Nullifier
    # marker, Somedoku global flag, or an unrecognized name — the decoder
    # warn-drops both unnamed and unrecognized, so a bare `Constant` with no
    # parseable integer stays unrecognized rather than silently becoming
    # `k = 0`.
    assert cosmetic_cage_kind(name) == expected


def test_marker_labels_covers_every_role() -> None:
    # MARKER_LABELS is the public role -> accepted-names table setter_guide.py's
    # cage-name-alias rows read directly; every name-bearing role
    # cosmetic_cage_kind recognizes has an entry here. `constant`'s only
    # static alias is `Nullifier` — `Constant <N>` is parameterized, not a
    # fixed name (ADR-0016).
    assert set(MARKER_LABELS) == {
        "killer",
        "equality",
        "rellik",
        "doubler",
        "s-cell",
        "constant",
        "somedoku",
    }


@pytest.mark.parametrize(
    "role",
    ["killer", "equality", "rellik", "doubler", "s-cell", "constant", "somedoku"],
)
def test_marker_labels_every_listed_name_classifies_to_its_role(role: str) -> None:
    # Every name MARKER_LABELS lists under a role must classify to that role
    # through cosmetic_cage_kind. MARKER_LABELS and cosmetic_cage_kind both
    # read naming's one registry, so the two cannot drift.
    for name in MARKER_LABELS[role]:
        assert cosmetic_cage_kind(name) == role


def test_doubler_named_cage_emits_modifier_directives_and_no_cage() -> None:
    # A `Doubler`-named cosmetic cage is a position marker, not a killer
    # cage: every cell it contains decodes to a discovered-modifier
    # directive, and the block emits no `cage`/`group-sum` at all (ADR-0012).
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {
                    "name": "Doubler",
                    "type": 2001,
                    "cages": [{"value": "", "cells": [0, 1]}],
                },
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives
    assert ModifierDirective("R1C2", is_modifier=True) in state.modifier_directives
    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)


@pytest.mark.parametrize(
    "name",
    ["Doubler", "doubler", "  DOUBLER  "],
    ids=["titlecase", "lowercase", "padded-upper"],
)
def test_doubler_marker_name_is_case_insensitive_and_trimmed(name: str) -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": name, "type": 2001, "cages": [{"value": "", "cells": [0]}]},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives
    assert Constraint("doubler") in puzzle.constraints


def test_doubler_marker_cell_with_a_given_still_decodes_both() -> None:
    # A doubler holds one digit worth twice its value — the marker and the
    # digit are orthogonal, so a given on a marked cell still lands.
    cells = list(EMPTY_CELLS)
    cells[0] = {"given": True, "value": 3}
    payload = encode_document(
        {
            "cells": cells,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {
                    "name": "Doubler",
                    "type": 2001,
                    "cages": [{"value": "", "cells": [0]}],
                },
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert Given("R1C1", 3) in puzzle.givens
    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives


def test_doubler_constraint_is_synthesized_once_across_marker_blocks() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "Doubler", "type": 2001, "cages": [{"cells": [0]}]},
                {"name": "Doubler", "type": 2001, "cages": [{"cells": [1]}]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.constraints.count(Constraint("doubler")) == 1


def test_a_red_cell_alone_is_not_a_doubler() -> None:
    # Declared doublers arrive only through a `Doubler` marker cage, so a bare
    # red `colors` bit carries no meaning and stands up no `doubler` constraint
    # or modifier directive.
    regions_4x4 = [(i // 4 // 2) * 2 + (i % 4 // 2) for i in range(16)]
    cells: list[dict[str, object]] = [{} for _ in range(16)]
    cells[0] = {"colors": 2}
    payload = encode_document(
        {
            "cells": cells,
            "size": 4,
            "constraints": [{"type": 0}, {"type": 1, "regions": regions_4x4}],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert Constraint("doubler") not in puzzle.constraints
    assert state.modifier_directives == ()


def test_constant_marker_cage_decodes_to_constant_constraint_and_modifiers() -> None:
    # A `Constant <N>`-named cosmetic cage is a position marker, not a killer
    # cage, exactly like `Doubler`: every cell it contains decodes to a
    # discovered-modifier directive, and the block emits no
    # `cage`/`group-sum` at all. Unlike `Doubler`, `k` rides on the name and
    # lands on the synthesized `constant` constraint's `value` param
    # (ADR-0016).
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {
                    "name": "Constant 5",
                    "type": 2001,
                    "cages": [{"cells": [0, 1]}],
                },
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives
    assert ModifierDirective("R1C2", is_modifier=True) in state.modifier_directives
    assert Constraint("constant", params={"value": 5}) in puzzle.constraints
    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)


def test_nullifier_marker_cage_decodes_as_constant_zero() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "Nullifier", "type": 2001, "cages": [{"cells": [0]}]},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives
    assert Constraint("constant", params={"value": 0}) in puzzle.constraints


@pytest.mark.parametrize(
    "name",
    ["Constant 5", "constant 5", "  CONSTANT   5  "],
    ids=["titlecase", "lowercase", "padded-upper-with-extra-space"],
)
def test_constant_marker_name_is_case_insensitive_and_trimmed(name: str) -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": name, "type": 2001, "cages": [{"cells": [0]}]},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives
    assert Constraint("constant", params={"value": 5}) in puzzle.constraints


def test_bare_constant_marker_cage_warns_and_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # No parseable integer in the name stays unrecognized (ADR-0016) — never
    # silently `k = 0`, the same warn-drop fate as any unrecognized name.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "Constant", "type": 2001, "cages": [{"cells": [0]}]},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert state.modifier_directives == ()
    assert all(c.type != "constant" for c in puzzle.constraints)
    assert "Constant" in capsys.readouterr().err


@pytest.mark.parametrize(
    "name",
    ["Doubler", "Constant 5"],
    ids=["doubler", "constant"],
)
def test_marker_cage_with_a_per_cage_value_field_is_refused(name: str) -> None:
    # A modifier's `k` is a puzzle-wide fact declared by the cage name; a
    # per-cage `value` field is a channel two cages could disagree on, so it
    # is refused outright rather than silently ignored (ADR-0016 decision 3).
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": name, "type": 2001, "cages": [{"value": "3", "cells": [0]}]},
            ],
        }
    )

    with pytest.raises(MalformedPuzzleError):
        link_to_puzzle(payload)


def test_link_mixing_doubler_and_constant_marker_cages_is_refused() -> None:
    # One modifier type per puzzle (ADR-0016 decision 4): a link declaring
    # both a Doubler and a Constant marker cage is refused rather than
    # silently merged.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "Doubler", "type": 2001, "cages": [{"cells": [0]}]},
                {"name": "Constant 5", "type": 2001, "cages": [{"cells": [1]}]},
            ],
        }
    )

    with pytest.raises(MalformedPuzzleError):
        link_to_puzzle(payload)


def test_two_constant_marker_cages_disagreeing_on_k_is_refused() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "Constant 5", "type": 2001, "cages": [{"cells": [0]}]},
                {"name": "Constant 7", "type": 2001, "cages": [{"cells": [1]}]},
            ],
        }
    )

    with pytest.raises(MalformedPuzzleError):
        link_to_puzzle(payload)


def test_two_constant_marker_cages_agreeing_on_k_decode_once() -> None:
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "Constant 5", "type": 2001, "cages": [{"cells": [0]}]},
                {"name": "Constant 5", "type": 2001, "cages": [{"cells": [1]}]},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert puzzle.constraints.count(Constraint("constant", params={"value": 5})) == 1
    assert ModifierDirective("R1C1", is_modifier=True) in state.modifier_directives
    assert ModifierDirective("R1C2", is_modifier=True) in state.modifier_directives


def test_s_cell_named_cage_declares_s_cells_and_emits_no_cage() -> None:
    # An `S-cell`-named cosmetic cage is a position marker, not a killer
    # cage: every cell it contains decodes to an S-cell working-state
    # directive (an empty cell has no marks, so it is a bare S-cell), and
    # the block emits no `cage`/`group-sum` at all.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {
                    "name": "S-cell",
                    "type": 2001,
                    "cages": [{"value": "", "cells": [0, 1]}],
                },
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert BareSCell("R1C1") in state.s_directives
    assert BareSCell("R1C2") in state.s_directives
    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2,7", SCellPin("R1C1", frozenset({2, 7}))),
        ("4", HalfSCell("R1C1", 4)),
        ("", BareSCell("R1C1")),
        (None, BareSCell("R1C1")),
        ("not-a-digit", BareSCell("R1C1")),
        ("1,2,3", BareSCell("R1C1")),
        ("35", SCellPin("R1C1", frozenset({3, 5}))),
    ],
    ids=[
        "pin",
        "half",
        "empty-string",
        "absent",
        "malformed-non-numeric",
        "malformed-too-many-parts",
        "scalar-shorthand",
    ],
)
def test_s_cell_marker_cage_value_selects_the_directive(
    value: object, expected: SDirective
) -> None:
    # The named cage's own `value` sources the pair/half/bare directive by
    # digit-count (ADR-0014): comma-split, or the two-digit scalar shorthand
    # in a single-digit domain (minDigit 0 -> 0..9). A malformed value falls
    # back to bare, the same reading as absent — never a crash.
    payload = _s_cell_cage_link(value)

    _, state = link_to_puzzle(payload)

    assert expected in state.s_directives


def test_s_cell_marker_center_marks_layer_a_restriction_not_a_candidate() -> None:
    # The cage `value` still picks the directive; the cell's own center marks
    # layer a consistency restriction over that directive, not an ordinary
    # candidate. So a caged cell yields both the cage's SCellPin and an
    # SCellMarkRestriction over its marks, and never an S-cell candidate.
    payload = _s_cell_cage_link("2,7", marks={1, 4, 9})

    _, state = link_to_puzzle(payload)

    assert SCellPin("R1C1", frozenset({2, 7})) in state.s_directives
    assert SCellMarkRestriction("R1C1", frozenset({1, 4, 9})) in state.s_directives
    assert all(c.address != "R1C1" for c in state.candidates)


def test_s_cell_marker_without_center_marks_emits_no_restriction() -> None:
    payload = _s_cell_cage_link("2,7")

    _, state = link_to_puzzle(payload)

    assert SCellPin("R1C1", frozenset({2, 7})) in state.s_directives
    assert not any(isinstance(d, SCellMarkRestriction) for d in state.s_directives)


def test_s_cell_marker_cage_value_out_of_domain_digit_is_refused_as_malformed() -> None:
    # A cage `value` naming a digit outside the board's domain rides into the
    # S-cell directive and is refused at verdict as malformed (CONTEXT.md,
    # "malformed"), exactly as an out-of-domain given is — never softened to a
    # bare S-cell that a wrong `found` could slip through.
    payload = _s_cell_cage_link("2,15")

    puzzle, state = link_to_puzzle(payload)

    assert SCellPin("R1C1", frozenset({2, 15})) in state.s_directives
    with pytest.raises(MalformedPuzzleError, match="15"):
        verdict(puzzle, state)


def test_s_cell_cage_value_1234_is_one_out_of_domain_half() -> None:
    # A value too long for the pin/half shorthand parses as one digit, not a
    # pair: `"1234"` is the half-cell digit 1234, never {1,2,3,4} and never
    # bare. No board holds 1234, so it is refused as malformed at verdict — the
    # same guard an out-of-domain given hits (CONTEXT.md, "malformed").
    payload = _s_cell_cage_link("1234")

    puzzle, state = link_to_puzzle(payload)

    assert HalfSCell("R1C1", 1234) in state.s_directives
    with pytest.raises(MalformedPuzzleError, match="1234"):
        verdict(puzzle, state)


def test_empty_s_cell_block_enables_schrodinger_by_presence() -> None:
    # Presence, not membership, stands up the mode: a named S-cell block that
    # names no cells still synthesizes the `schrodinger` constraint and widens
    # the domain to 0…N, leaving every cell's `is_s` free for the solver to
    # discover. Naming nothing pins nothing — no cell is a known S-cell.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "S-cell", "type": 2001, "cages": []},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert Constraint("schrodinger") in puzzle.constraints
    assert puzzle.board == Board(size=9, values=range(10))
    assert state.s_directives == ()


def test_named_s_cell_block_still_pins_its_cells_as_known_s_cells() -> None:
    # Presence-enablement does not weaken membership: a block that names a cell
    # still pins it as a known S-cell from the cage `value`, on top of the mode
    # the block's presence enables (ADR-0014).
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {
                    "name": "S-cell",
                    "type": 2001,
                    "cages": [{"value": "2,3", "cells": [0]}],
                },
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert Constraint("schrodinger") in puzzle.constraints
    assert SCellPin("R1C1", frozenset({2, 3})) in state.s_directives


def test_no_s_cell_block_keeps_plain_domain_and_no_schrodinger() -> None:
    # The opt-in boundary: a puzzle carrying no named S-cell block keeps its
    # ordinary 1…N domain and synthesizes no `schrodinger` constraint. Only a
    # link that names the cage opts into the widened domain and the mode.
    payload = encode_document({"cells": EMPTY_CELLS, "constraints": WIRE_CONSTRAINTS})

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.board == Board(size=9, values=range(1, 10))
    assert Constraint("schrodinger") not in puzzle.constraints


@pytest.mark.parametrize(
    "name",
    ["S-cell", "s-cell", "Schrödinger", "Schrodinger", "  SCHRODINGER  "],
    ids=["s-cell", "lowercase", "schrodinger-umlaut", "schrodinger-ascii", "padded"],
)
def test_s_cell_marker_name_is_recognized_case_insensitive_and_trimmed(
    name: str,
) -> None:
    # Each S-cell alias joins the recognized-name set, so it declares S-cells
    # rather than tripping the unknown-name refusal.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": name, "type": 2001, "cages": [{"cells": [0]}]},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert BareSCell("R1C1") in state.s_directives
    assert Constraint("schrodinger") in puzzle.constraints


def test_schrodinger_marker_reads_domain_and_synthesizes_constraint() -> None:
    payload = _schrodinger_link(EMPTY_CELLS, min_digit=0)

    puzzle, _ = link_to_puzzle(payload)

    assert puzzle.board == Board(size=9, values=range(10))
    assert Constraint("schrodinger") in puzzle.constraints


def test_schrodinger_marker_ignores_cosmetic_and_disabled_constraints() -> None:
    # The real link's constraints include cosmetic types the classic-only guard
    # would otherwise reject outright, plus a disabled duplicate of the regions
    # matrix — both ignored once a marker makes the link Schrödinger.
    payload = _schrodinger_link(EMPTY_CELLS)

    puzzle, _ = link_to_puzzle(payload)

    regions_constraint = next(
        c for c in puzzle.constraints if c.type == "regions-distinct"
    )
    assert regions_constraint == Constraint("regions-distinct")


@pytest.mark.parametrize(
    "cell",
    [{"value": 5}, {"given": True, "value": 5}],
    ids=["placement", "given"],
)
def test_s_cell_marker_on_a_settled_value_emits_both_directives(
    cell: dict[str, object],
) -> None:
    # A marked cell is declared an S-cell (bare, no cage value here) while its
    # own settled digit is a singleton pin — the is-S-vs-settled contradiction
    # decodes cleanly as both directives, leaving the solver to report the
    # collision as broke rather than a hard decode error.
    cells = list(EMPTY_CELLS)
    cells[0] = cell
    payload = encode_document(
        {
            "cells": cells,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"name": "S-cell", "type": 2001, "cages": [{"cells": [0]}]},
            ],
        }
    )

    _, state = link_to_puzzle(payload)

    assert BareSCell("R1C1") in state.s_directives
    assert SingletonPin("R1C1", 5) in state.s_directives


def test_s_cell_marker_synthesizes_schrodinger_once_amid_cosmetics() -> None:
    # An S-cell marker cage alongside a real link's cosmetic constraint mix
    # (including a `type 2003` block) widens the domain once and synthesizes
    # exactly one `schrodinger` constraint, and the marker cage's own
    # cage-value pinned pair still decodes.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "minDigit": 0,
            "constraints": [
                *_SCHRODINGER_WIRE_CONSTRAINTS,
                {
                    "name": "S-cell",
                    "type": 2001,
                    "cages": [{"value": "2,7", "cells": [0]}],
                },
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert puzzle.board == Board(size=9, values=range(10))
    assert puzzle.constraints.count(Constraint("schrodinger")) == 1
    assert SCellPin("R1C1", frozenset({2, 7})) in state.s_directives


@pytest.mark.parametrize(
    "cell",
    [{"value": 5}, {"given": True, "value": 5}],
    ids=["placement", "given"],
)
def test_settled_value_on_a_non_marker_cell_is_a_singleton_pin_under_schrodinger(
    cell: dict[str, object],
) -> None:
    # A settled large digit means "this cell is exactly d, not an S-cell"
    # (ADR-0014): under a Schrödinger layer it routes to a singleton pin
    # regardless of the given/placement wire distinction, not a plain
    # given/placement that would leave is_s free for the solver to lift.
    cells = list(EMPTY_CELLS)
    cells[1] = cell
    payload = _schrodinger_link(cells)

    puzzle, state = link_to_puzzle(payload)

    assert SingletonPin("R1C2", 5) in state.s_directives
    assert puzzle.givens == ()
    assert state.places == ()


def test_a_single_link_decodes_both_doubler_and_s_cell_markers() -> None:
    # Named marker cages carry the variant, so one link may hold both — a
    # `Doubler` block and an `S-cell` block side by side, each decoded.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {
                    "name": "S-cell",
                    "type": 2001,
                    "cages": [{"value": "2,7", "cells": [0]}],
                },
                {"name": "Doubler", "type": 2001, "cages": [{"cells": [1]}]},
            ],
        }
    )

    puzzle, state = link_to_puzzle(payload)

    assert Constraint("schrodinger") in puzzle.constraints
    assert Constraint("doubler") in puzzle.constraints
    assert SCellPin("R1C1", frozenset({2, 7})) in state.s_directives
    assert ModifierDirective("R1C2", is_modifier=True) in state.modifier_directives
    # The S-cell marker widened the domain by the classic k=1 extra digit,
    # defaulting to 0 at the bottom: 0…N.
    assert puzzle.board == Board(size=9, values=range(10))


def _marker_link(
    *, s_cell_cages: list[dict[str, object]], doubler_cages: list[dict[str, object]]
) -> dict[str, object]:
    """A synthesised document (not yet lz-compressed) carrying an `S-cell`
    block only when `s_cell_cages` is non-empty, a `Doubler` block only when
    `doubler_cages` is non-empty, and an ordinary `Sum`-named killer cage
    always — a link only ever carries a marker block for a type it actually
    uses, which is what makes "the marker types present in this link" a
    meaningful set for `colorize_marker_cages` to read."""
    marker_blocks: list[dict[str, object]] = []
    if s_cell_cages:
        marker_blocks.append({"name": "S-cell", "type": 2001, "cages": s_cell_cages})
    if doubler_cages:
        marker_blocks.append({"name": "Doubler", "type": 2001, "cages": doubler_cages})
    return {
        "formatVersion": "1.5.0",
        "puzzle": {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                *marker_blocks,
                {
                    "name": "Sum",
                    "type": 2001,
                    "cages": [{"value": "7", "cells": [2, 3]}],
                },
            ],
        },
    }


def _blocks_by_name(document: dict[str, object]) -> dict[str, dict[str, Any]]:
    puzzle_data = cast("dict[str, object]", document["puzzle"])
    constraints = cast("list[dict[str, Any]]", puzzle_data["constraints"])
    return {block["name"]: block for block in constraints if block.get("type") == 2001}


def test_colorize_makes_a_lone_s_cell_marker_red() -> None:
    # Exactly one marker type on the link (S-cell, no Doubler block at all) ⇒
    # that type takes palette[0] (red), whichever type it is.
    document = _marker_link(
        s_cell_cages=[{"value": "2,7", "cells": [0]}], doubler_cages=[]
    )

    colored = colorize_marker_cages(document)

    style = _blocks_by_name(colored)["S-cell"]["style"]
    # Both the cage outline and the label text take the marker color, the full
    # style shape SudokuMaker needs to render the cosmetic-cage icon.
    assert style["cage"]["color"] == _MARKER_COLOR_PALETTE[0]
    assert style["text"]["color"] == _MARKER_COLOR_PALETTE[0]
    assert "Doubler" not in _blocks_by_name(colored)


def test_colorize_makes_a_lone_doubler_marker_red() -> None:
    # A Doubler-only link colors its cages red too — red is the lone-type
    # slot, not an S-cell-specific color.
    document = _marker_link(s_cell_cages=[], doubler_cages=[{"cells": [1]}])

    colored = colorize_marker_cages(document)

    assert (
        _blocks_by_name(colored)["Doubler"]["style"]["cage"]["color"]
        == _MARKER_COLOR_PALETTE[0]
    )
    assert "S-cell" not in _blocks_by_name(colored)


def test_colorize_prefers_s_cell_for_red_when_both_types_present() -> None:
    # Two marker types contend for red; S-cell wins it by priority and
    # Doubler falls to the next palette slot.
    document = _marker_link(
        s_cell_cages=[{"value": "2,7", "cells": [0]}],
        doubler_cages=[{"cells": [1]}],
    )

    colored = colorize_marker_cages(document)

    blocks = _blocks_by_name(colored)
    assert blocks["S-cell"]["style"]["cage"]["color"] == _MARKER_COLOR_PALETTE[0]
    assert blocks["Doubler"]["style"]["cage"]["color"] == _MARKER_COLOR_PALETTE[1]


def test_colorize_leaves_an_ordinary_named_cage_uncolored() -> None:
    document = _marker_link(
        s_cell_cages=[{"value": "2,7", "cells": [0]}],
        doubler_cages=[{"cells": [1]}],
    )

    colored = colorize_marker_cages(document)

    assert "style" not in _blocks_by_name(colored)["Sum"]


def test_colorize_does_not_mutate_its_input() -> None:
    document = _marker_link(
        s_cell_cages=[{"value": "2,7", "cells": [0]}],
        doubler_cages=[{"cells": [1]}],
    )
    before = json.loads(json.dumps(document))

    colorize_marker_cages(document)

    assert document == before


def test_colorizing_an_emitted_link_does_not_change_its_decode() -> None:
    # Color is write-only decoration: a decode of the colored link must agree
    # exactly with a decode of the uncolored one (CODING_STANDARDS.md — cosmetic
    # only, never a decode input).
    document = _marker_link(
        s_cell_cages=[{"value": "2,7", "cells": [0]}],
        doubler_cages=[{"cells": [1]}],
    )
    plain_link = document_to_link(document)
    colored_link = document_to_link(colorize_marker_cages(document))

    assert link_to_puzzle(colored_link) == link_to_puzzle(plain_link)
