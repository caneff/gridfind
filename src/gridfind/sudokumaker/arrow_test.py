"""Decode behaviour of the `type 408` arrow blocks: each `bulbsWithArrows`
entry decodes to one `arrow` `Constraint` carrying that entry's bulb and
shaft cell addresses, order preserved; a disabled block decodes to nothing
quietly. Decode itself never refuses an empty bulb, an empty `arrows` list,
or a zero-cell shaft — the `Arrow` layer raises at emit
(`layers/arrow_test.py`), not decode.
"""

from __future__ import annotations

import pytest

from gridfind.puzzle import Constraint
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.conftest import constraint_link


def _arrow(*bulbs_with_arrows: dict[str, object]) -> dict[str, object]:
    return {"type": 408, "bulbsWithArrows": list(bulbs_with_arrows)}


def test_a_single_bulb_and_shaft_decodes_to_one_arrow_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(_arrow({"bulbCells": [0], "arrows": [[1, 2]]}))

    puzzle, _ = link_to_puzzle(payload)

    arrows = [c for c in puzzle.constraints if c.type == "arrow"]
    assert arrows == [
        Constraint("arrow", params={"bulb": ["R1C1"], "arrows": [["R1C2", "R1C3"]]})
    ]
    assert capsys.readouterr().err == ""


def test_one_bulb_with_two_shafts_decodes_to_one_constraint_carrying_both(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(_arrow({"bulbCells": [0], "arrows": [[1, 2], [9, 18]]}))

    puzzle, _ = link_to_puzzle(payload)

    arrows = [c for c in puzzle.constraints if c.type == "arrow"]
    assert arrows == [
        Constraint(
            "arrow",
            params={
                "bulb": ["R1C1"],
                "arrows": [["R1C2", "R1C3"], ["R2C1", "R3C1"]],
            },
        )
    ]
    assert capsys.readouterr().err == ""


def test_two_bulb_entries_in_one_block_decode_to_two_constraints(
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = constraint_link(
        _arrow(
            {"bulbCells": [0], "arrows": [[1, 2]]},
            {"bulbCells": [3], "arrows": [[4, 5]]},
        )
    )

    puzzle, _ = link_to_puzzle(payload)

    arrows = [c for c in puzzle.constraints if c.type == "arrow"]
    assert arrows == [
        Constraint("arrow", params={"bulb": ["R1C1"], "arrows": [["R1C2", "R1C3"]]}),
        Constraint("arrow", params={"bulb": ["R1C4"], "arrows": [["R1C5", "R1C6"]]}),
    ]
    assert capsys.readouterr().err == ""


def test_disabled_arrow_block_decodes_to_nothing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    block = _arrow({"bulbCells": [0], "arrows": [[1, 2]]})
    block["disabled"] = True
    payload = constraint_link(block)

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type != "arrow" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("entry", "expected_params"),
    [
        pytest.param(
            {"bulbCells": [], "arrows": [[1, 2]]},
            {"bulb": [], "arrows": [["R1C2", "R1C3"]]},
            id="empty-bulb",
        ),
        pytest.param(
            {"bulbCells": [0], "arrows": []},
            {"bulb": ["R1C1"], "arrows": []},
            id="no-arrows",
        ),
        pytest.param(
            {"bulbCells": [0], "arrows": [[]]},
            {"bulb": ["R1C1"], "arrows": [[]]},
            id="zero-cell-shaft",
        ),
    ],
)
def test_decode_never_refuses_a_malformed_entry(
    entry: dict[str, object],
    expected_params: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Decode carries a malformed entry through unchanged; the `Arrow` layer
    # is the one home that raises `MalformedPuzzleError` for it, at emit.
    payload = constraint_link(_arrow(entry))

    puzzle, _ = link_to_puzzle(payload)

    arrows = [c for c in puzzle.constraints if c.type == "arrow"]
    assert arrows == [Constraint("arrow", params=expected_params)]
    assert capsys.readouterr().err == ""
