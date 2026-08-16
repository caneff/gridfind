"""`registry`: the `DECODER_REGISTRY` table and the decode policy it drives.

The registry is what `decode_link` consults to decide what each wire type is —
structural (givens/regions), a modeled constraint, or unmodeled. This file
pins the whole-decode behavior that follows from that table: the canonical
classic decode, the loud-drop policy for an unmodeled constraint carrying live
data versus the quiet pass for an inert or disabled one, the global toggles,
and the setter-doc each modeled row owes the accepted-link guide.
"""

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import DECODER_REGISTRY, decode_link, encode_link
from gridfind.sudokumaker.conftest import (
    CLASSIC_CONSTRAINTS,
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    constraint_link,
    encode_document,
)


def test_inert_unmodeled_constraints_decode_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A real link routinely carries cosmetic or empty extras: an
    # empty unmodeled clue list, cosmetic pen-lines, an empty group. None
    # emits a rule, so the puzzle is identical to one without them and
    # nothing warns.
    with_extras = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"type": 250, "clues": []},  # empty, unmodeled clue list
                {"type": 2000, "lines": [[0, 1]]},  # cosmetic pen-lines
                {"type": 303, "input": {"groups": [{"cells": []}]}},  # empty group
            ],
        }
    )
    plain = encode_document({"cells": EMPTY_CELLS, "constraints": WIRE_CONSTRAINTS})

    puzzle_extras, state_extras = decode_link(with_extras)
    puzzle_plain, state_plain = decode_link(plain)

    assert puzzle_extras == puzzle_plain
    assert state_extras == state_plain
    assert capsys.readouterr().err == ""


def test_active_unmodeled_constraint_decodes_with_named_stderr_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A constraint carrying live data is dropped, not rejected: the verdict is
    # the reduced-ruleset answer, stderr names the dropped constraint (its
    # `definition.name` and type) so the drop is never silent, and stdout (the
    # verdict channel) is untouched.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {
                    "type": 1000,
                    "clues": [{"cell": 0}],
                    "definition": {"name": "Same Difference Lines"},
                },
            ],
        }
    )

    puzzle, _ = decode_link(payload)

    captured = capsys.readouterr()
    assert puzzle.constraints == CLASSIC_CONSTRAINTS
    assert "Same Difference Lines" in captured.err
    assert "1000" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "live_payload",
    [
        {"clues": [{"cell": 0}]},
        {"negative": [1]},
        {"input": {"groups": [{"cells": [0, 1]}]}},
        {"cages": [{"cells": [0, 1], "value": 5}]},
    ],
    ids=["clues", "negative", "input-groups", "cages"],
)
def test_every_live_payload_shape_warns(
    live_payload: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    # Live data reaches gridfind under any of four shapes; each must trip the
    # loud drop, matching scripts/inspect_link.py's classification.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [*WIRE_CONSTRAINTS, {"type": 1000, **live_payload}],
        }
    )

    decode_link(payload)

    assert "1000" in capsys.readouterr().err


@pytest.mark.parametrize(
    "name",
    ["Sum", "Killer", "Doubler", "S-cell", "Schrödinger", "  sum  "],
    ids=["sum", "killer", "doubler", "s-cell", "schrodinger", "padded-lower"],
)
def test_cage_shaped_name_on_a_type_1000_constraint_warns_and_names_it(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # A cage-selector (Sum/Killer) or cell-marker (Doubler/S-cell/Schrödinger)
    # name needs a cage's cells; a type 1000 custom constraint has none, so the
    # shared recognizer's carrier-fitness check fails and it warn-drops, naming
    # the component that was stranded on the wrong carrier.
    payload = constraint_link({"type": 1000, "definition": {"name": name}})

    puzzle, _ = decode_link(payload)

    captured = capsys.readouterr()
    assert puzzle.constraints == CLASSIC_CONSTRAINTS
    assert name in captured.err
    assert "1000" in captured.err


def test_disabled_cage_shaped_name_on_type_1000_is_skipped_without_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # `disabled` wins over the misplaced-name check too: the setter switched
    # the block off, so a stranded `Sum` name never warns.
    payload = constraint_link(
        {"type": 1000, "definition": {"name": "Sum"}, "disabled": True}
    )

    decode_link(payload)

    assert capsys.readouterr().err == ""


def test_disabled_active_constraint_is_skipped_without_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A disabled constraint is one the setter switched off — skipped before the
    # active/inert check, so even a live payload never warns.
    payload = encode_document(
        {
            "cells": EMPTY_CELLS,
            "constraints": [
                *WIRE_CONSTRAINTS,
                {"type": 1000, "clues": [{"cell": 0}], "disabled": True},
            ],
        }
    )

    decode_link(payload)

    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("block", "constraint_type"),
    [
        pytest.param({"type": 12}, "anti-king", id="anti-king"),
        pytest.param({"type": 13}, "anti-knight", id="anti-knight"),
        # The real diagonal blocks carry a cosmetic `style` alongside the type;
        # it is purely visual, so the toggle still decodes to its constraint.
        pytest.param(
            {"type": 10, "style": {"color": "#34bbe6ff", "thickness": 0.02}},
            "negative-diagonal",
            id="negative-diagonal",
        ),
        pytest.param(
            {"type": 11, "style": {"color": "#34bbe6ff", "thickness": 0.02}},
            "positive-diagonal",
            id="positive-diagonal",
        ),
    ],
)
def test_global_toggle_round_trips_through_encode_and_decode(
    block: dict[str, object], constraint_type: str
) -> None:
    # Each global toggle decodes to its gridfind constraint, and encode_link
    # reverses it: a document carrying the wire block survives encode -> decode
    # with the matching Constraint present.
    document: dict[str, object] = {
        "formatVersion": "1.5.0",
        "puzzle": {"cells": EMPTY_CELLS, "constraints": [*WIRE_CONSTRAINTS, block]},
    }

    puzzle, _ = decode_link(encode_link(document))

    assert Constraint(type=constraint_type) in puzzle.constraints


@pytest.mark.parametrize(
    "wire_type",
    [t for t in DECODER_REGISTRY if t not in (0, 1)],
)
def test_non_structural_registry_rows_carry_a_populated_setter_doc(
    wire_type: int,
) -> None:
    # Every setter-facing constraint owes the accepted-link setter guide its
    # display name, wire block, decode result, and verdict (map #335, #336).
    setter_doc = DECODER_REGISTRY[wire_type].setter_doc
    assert setter_doc is not None
    assert setter_doc.display_name
    assert setter_doc.wire_block
    assert setter_doc.decode_result
    assert setter_doc.verdict


@pytest.mark.parametrize("wire_type", [0, 1])
def test_structural_registry_rows_carry_no_setter_doc(wire_type: int) -> None:
    # `type 0` (givens) and `type 1` (regions) aren't setter-drawn constraints,
    # so `None` marks them as not setter-facing without a separate skip-list.
    assert DECODER_REGISTRY[wire_type].setter_doc is None
