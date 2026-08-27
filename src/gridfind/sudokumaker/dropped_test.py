"""`dropped`: the decode-time drop policy for constraints `DECODER_REGISTRY`
does not model — the loud-drop path for one carrying live data versus the
quiet pass for an inert or disabled one, exercised through `link_to_puzzle` (the
public seam this policy runs behind on every decode).
"""

import pytest

from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import (
    CLASSIC_CONSTRAINTS,
    EMPTY_CELLS,
    WIRE_CONSTRAINTS,
    constraint_link,
    encode_document,
)
from gridfind.sudokumaker.dropped import has_live_data


@pytest.mark.parametrize(
    ("cells", "live"),
    [([0], True), ([5], True), ([], False)],
    ids=["index-0", "index-nonzero", "empty"],
)
def test_cells_liveness_counts_index_zero(cells: list[int], live: bool) -> None:
    # A cells-based constraint (indexing marks its control cell here) is live
    # when the list is non-empty. Raw index 0 is R1C1, a real cell — the
    # liveness check must read the list's length, not the truthiness of its
    # entries, or a constraint on R1C1 reads as inert.
    assert has_live_data({"type": 600, "cells": cells}) is live


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
                {"type": 250, "clues": []},
                {"type": 2000, "lines": [[0, 1]]},
                {"type": 302, "groups": [[]]},
            ],
        }
    )
    plain = encode_document({"cells": EMPTY_CELLS, "constraints": WIRE_CONSTRAINTS})

    puzzle_extras, state_extras = link_to_puzzle(with_extras)
    puzzle_plain, state_plain = link_to_puzzle(plain)

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

    puzzle, _ = link_to_puzzle(payload)

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

    link_to_puzzle(payload)

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

    puzzle, _ = link_to_puzzle(payload)

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

    link_to_puzzle(payload)

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

    link_to_puzzle(payload)

    assert capsys.readouterr().err == ""
