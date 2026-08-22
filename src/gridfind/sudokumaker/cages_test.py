"""`cages`: the caged-region families — killer cages (type 301), the cosmetic
cage's graduation to a killer cage (type 2001, ADR-0008), and thermometers
(type 300).

Each decodes through `link_to_puzzle` to its gridfind constraint(s). A summed cage
recomposes into a no-repeats `cage` plus a `group-sum` over the same cells
(ADR-0009); a cosmetic cage carrying a numeric label graduates the same way.
The named-marker cages (`Doubler`, `S-cell`) are a different reading and live
in `markers_test`; here a name is either a `Sum`/`Killer` label that selects
the killer-cage rule, an `Equality` label that selects `cage` + `equality-cage`,
a `Rellik`/`Anti` label that selects the anti-cage subset-sum ban (ADR-0018), or
an unnamed/unrecognized one the decoder warn-drops (ADR-0012).
"""

import pytest

from gridfind.puzzle import Constraint, ModifierDirective
from gridfind.sudokumaker import link_to_puzzle
from gridfind.sudokumaker.cages import _CosmeticCageDecode, _decode_cosmetic_block
from gridfind.sudokumaker.conftest import constraint_link


def test_cage_decodes_to_region_only_cage_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A no-sum cage (value 0) is honored silently as a plain region-only cage,
    # its raw indices mapped row-major to addresses ([18, 19] -> R3C1, R3C2).
    payload = constraint_link({"type": 301, "cages": [{"cells": [18, 19], "value": 0}]})

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R3C1", "R3C2"]}) in puzzle.constraints
    assert capsys.readouterr().err == ""


def test_cage_with_a_sum_decodes_to_a_cage_plus_a_group_sum(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A summed cage (value > 0) decodes to two constraints over the same
    # cells: a no-repeats `cage` and the total as a `group-sum` — the killer
    # cage's recomposition (ADR-0009). No warning, the sum is honored.
    payload = constraint_link({"type": 301, "cages": [{"cells": [0, 1], "value": 7}]})

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 7})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_multiple_cages_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {
            "type": 301,
            "cages": [
                {"cells": [0, 1], "value": 0},
                {"cells": [18, 19], "value": 0},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert Constraint("cage", params={"cells": ["R3C1", "R3C2"]}) in puzzle.constraints


def test_cosmetic_cage_with_numeric_label_decodes_to_a_killer_cage_constraint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A numeric string `value` is the only channel an out-of-range killer sum
    # (a doubler inside a cage) reaches gridfind through, so it graduates to a
    # `cage` plus the total as a `group-sum` over the same cells. Cells and
    # value nest under `cages`, the same wire shape as a `type 301` block.
    payload = constraint_link(
        {"name": "Sum", "type": 2001, "cages": [{"value": "11", "cells": [0, 1, 2]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("cage", params={"cells": ["R1C1", "R1C2", "R1C3"]})
        in puzzle.constraints
    )
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2", "R1C3"], "sum": 11})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


def test_named_cosmetic_cage_with_a_zero_label_decodes_to_a_bare_cage() -> None:
    # A `"0"` label carries no killer sum — a zero total is no total, the same
    # rule a sumless `type 301` and a non-numeric label both decode to: a
    # no-repeats `cage` with no `group-sum`.
    payload = constraint_link(
        {"name": "Killer", "type": 2001, "cages": [{"value": "0", "cells": [0, 1]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert all(c.type != "group-sum" for c in puzzle.constraints)


@pytest.mark.parametrize(
    "label",
    ["Total", ""],
    ids=["non-numeric-label", "empty-label"],
)
def test_named_cosmetic_cage_without_a_numeric_label_decodes_to_a_bare_cage(
    label: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A label carrying no killer sum still leaves a rule: every non-disabled
    # named killer cage emits a no-repeats `cage` with no `group-sum`, exactly
    # like a sumless `type 301`.
    payload = constraint_link(
        {"name": "Sum", "type": 2001, "cages": [{"value": label, "cells": [0, 1]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert all(c.type != "group-sum" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "name",
    ["Sum", "killer", "  Killer  ", "SUM"],
    ids=["sum-titlecase", "killer-lowercase", "killer-padded", "sum-upper"],
)
def test_named_sum_or_killer_cage_decodes_as_a_killer_cage(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # A cage named `Sum`/`Killer` (any case, surrounding whitespace) selects
    # the killer-cage rule, the name itself discarded once recognized
    # (ADR-0012).
    payload = constraint_link(
        {"name": name, "type": 2001, "cages": [{"value": "7", "cells": [0, 1]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 7})
        in puzzle.constraints
    )
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "name",
    ["Equality", "equality", "  Equality  ", "EQUALITY"],
    ids=[
        "equality-titlecase",
        "equality-lowercase",
        "equality-padded",
        "equality-upper",
    ],
)
def test_named_equality_cage_decodes_to_cage_plus_equality_cage(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # A cage named `Equality` (any case, surrounding whitespace) selects the
    # equality-cage rule: a no-repeats `cage` plus `equality-cage` over the
    # same cells — the cage's `value` label is never read, unlike
    # a killer cage's numeric total.
    payload = constraint_link(
        {"name": name, "type": 2001, "cages": [{"value": "7", "cells": [0, 1]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("equality-cage", params={"cells": ["R1C1", "R1C2"]})
        in puzzle.constraints
    )
    assert all(c.type != "group-sum" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "name",
    ["Rellik", "anti", "  Anti  ", "RELLIK"],
    ids=["rellik-titlecase", "anti-lowercase", "anti-padded", "rellik-upper"],
)
def test_named_rellik_or_anti_cage_decodes_as_a_rellik_cage(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # A cage named `Rellik`/`Anti` (any case, surrounding whitespace) selects
    # the anti-cage subset-sum ban (ADR-0018): a no-repeats `cage` plus a
    # `rellik-cage` carrying the label as the forbidden total.
    payload = constraint_link(
        {"name": name, "type": 2001, "cages": [{"value": "7", "cells": [0, 1]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("rellik-cage", params={"cells": ["R1C1", "R1C2"], "sum": 7})
        in puzzle.constraints
    )
    assert all(c.type != "group-sum" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_multiple_named_equality_cages_each_decode_to_their_own_constraint() -> None:
    # One block carries many cages under `cages`, exactly as a `type 301`
    # block does.
    payload = constraint_link(
        {
            "name": "Equality",
            "type": 2001,
            "cages": [
                {"cells": [0, 1]},
                {"cells": [18, 19]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("equality-cage", params={"cells": ["R1C1", "R1C2"]})
        in puzzle.constraints
    )
    assert Constraint("cage", params={"cells": ["R3C1", "R3C2"]}) in puzzle.constraints
    assert (
        Constraint("equality-cage", params={"cells": ["R3C1", "R3C2"]})
        in puzzle.constraints
    )


def test_named_equality_cage_with_an_odd_cell_count_still_decodes() -> None:
    # Decode itself never refuses an odd cell count — `equality-cage` raises
    # `MalformedPuzzleError` once the puzzle reaches emit, not
    # here. The decoder's job is only to graduate the named block.
    payload = constraint_link(
        {"name": "Equality", "type": 2001, "cages": [{"cells": [0, 1, 2]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("cage", params={"cells": ["R1C1", "R1C2", "R1C3"]})
        in puzzle.constraints
    )
    assert (
        Constraint("equality-cage", params={"cells": ["R1C1", "R1C2", "R1C3"]})
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "label",
    ["0", "Total", ""],
    ids=["zero-label", "non-numeric-label", "empty-label"],
)
def test_named_rellik_cage_without_a_numeric_label_decodes_to_a_bare_cage(
    label: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A label carrying no forbidden total still leaves a rule: a no-repeats
    # `cage` with no `rellik-cage`, exactly like a sumless killer cage.
    payload = constraint_link(
        {"name": "Rellik", "type": 2001, "cages": [{"value": label, "cells": [0, 1]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert all(c.type != "rellik-cage" for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_multiple_named_cosmetic_cages_each_decode_to_their_own_constraint() -> None:
    # One block carries many cages under `cages`, exactly as a `type 301`
    # block does — a real doubler export packs two cages into one block.
    payload = constraint_link(
        {
            "name": "Sum",
            "type": 2001,
            "cages": [
                {"value": "7", "cells": [0, 1]},
                {"value": "11", "cells": [18, 19]},
            ],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in puzzle.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 7})
        in puzzle.constraints
    )
    assert Constraint("cage", params={"cells": ["R3C1", "R3C2"]}) in puzzle.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R3C1", "R3C2"], "sum": 11})
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    "cages",
    [
        [{"value": "11", "cells": [0, 1, 2]}],
        [{"value": "0", "cells": [0, 1]}],
        [{"value": "Total", "cells": [0, 1]}],
        [{"value": "", "cells": [0, 1]}],
        [{"value": "7", "cells": [0, 1]}, {"value": "11", "cells": [18, 19]}],
    ],
    ids=[
        "numeric-value",
        "zero-value",
        "non-numeric-value",
        "empty-value",
        "multiple-cages",
    ],
)
def test_unnamed_cosmetic_cage_warns_and_drops(
    cages: list[dict[str, object]], capsys: pytest.CaptureFixture[str]
) -> None:
    # An unnamed block carries no rule under any value shape — only a
    # recognized name selects one (ADR-0012). No cage/group-sum constraint is
    # emitted for it, and the drop is loud.
    payload = constraint_link({"type": 2001, "cages": cages})

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)
    assert "unnamed cosmetic cage" in capsys.readouterr().err


def test_unrecognized_named_cage_warns_and_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # An unfamiliar name is dropped rather than silently honored under a
    # guessed ruleset — "Foobar" stays unrecognized forever (ADR-0012).
    payload = constraint_link(
        {"name": "Foobar", "type": 2001, "cages": [{"value": "7", "cells": [0, 1]}]}
    )

    puzzle, _ = link_to_puzzle(payload)

    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)
    assert "Foobar" in capsys.readouterr().err


def test_normal_thermo_decodes_to_ordered_path_constraint() -> None:
    # Raw indices map row-major to addresses, bulb first, order preserved —
    # [0, 1, 2] -> R1C1, R1C2, R1C3.
    payload = constraint_link({"type": 300, "slow": False, "thermometers": [[0, 1, 2]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": False})
        in puzzle.constraints
    )


def test_multiple_thermo_paths_each_decode_to_their_own_constraint() -> None:
    payload = constraint_link(
        {
            "type": 300,
            "slow": False,
            "thermometers": [[0, 1, 2], [9, 18, 27]],
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": False})
        in puzzle.constraints
    )
    assert (
        Constraint("thermo", params={"path": ["R2C1", "R3C1", "R4C1"], "slow": False})
        in puzzle.constraints
    )


def test_slow_thermo_decodes_with_slow_true_on_the_constraint() -> None:
    payload = constraint_link({"type": 300, "slow": True, "thermometers": [[0, 1, 2]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": True})
        in puzzle.constraints
    )


def test_two_cell_thermo_decodes_the_bare_inequality_path() -> None:
    payload = constraint_link({"type": 300, "slow": False, "thermometers": [[0, 1]]})

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2"], "slow": False})
        in puzzle.constraints
    )


def test_thermo_style_is_ignored() -> None:
    payload = constraint_link(
        {
            "type": 300,
            "slow": False,
            "thermometers": [[0, 1, 2]],
            "style": {"color": "#ff0000", "thickness": 5},
        }
    )

    puzzle, _ = link_to_puzzle(payload)

    assert (
        Constraint("thermo", params={"path": ["R1C1", "R1C2", "R1C3"], "slow": False})
        in puzzle.constraints
    )


@pytest.mark.parametrize(
    ("block", "decoded_types"),
    [
        pytest.param(
            {"type": 301, "cages": [{"cells": [0, 1], "value": 7}], "disabled": True},
            ("cage",),
            id="cage-disabled",
        ),
        pytest.param({"type": 301, "cages": []}, ("cage",), id="cage-empty"),
        pytest.param(
            {
                "type": 2001,
                "cages": [{"value": "7", "cells": [0, 1]}],
                "disabled": True,
            },
            ("cage",),
            id="cosmetic-cage-disabled",
        ),
        pytest.param({"type": 2001, "cages": []}, ("cage",), id="cosmetic-cage-empty"),
        pytest.param(
            {"type": 300, "slow": False, "thermometers": [[0, 1]], "disabled": True},
            ("thermo",),
            id="thermo-disabled",
        ),
        pytest.param(
            {"type": 300, "slow": False, "thermometers": []},
            ("thermo",),
            id="thermo-empty",
        ),
    ],
)
def test_disabled_or_empty_caged_block_decodes_to_nothing_quietly(
    block: dict[str, object],
    decoded_types: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A disabled block (setter switched it off) and an empty one (no cages/paths)
    # both add no constraint and warn nothing.
    puzzle, _ = link_to_puzzle(constraint_link(block))

    assert all(c.type not in decoded_types for c in puzzle.constraints)
    assert capsys.readouterr().err == ""


def test_decode_cosmetic_block_returns_killer_constraints_with_no_declaration() -> None:
    # A pure call, no loop: `kind` selects the killer-cage rule and the
    # declaration slot stays `None` — only a modifier-marked block with cells
    # returns one.
    decode, declaration = _decode_cosmetic_block(
        "killer", {"name": "Sum"}, [{"value": "7", "cells": [0, 1]}], size=9
    )

    assert Constraint("cage", params={"cells": ["R1C1", "R1C2"]}) in decode.constraints
    assert (
        Constraint("group-sum", params={"cells": ["R1C1", "R1C2"], "sum": 7})
        in decode.constraints
    )
    assert declaration is None


def test_decode_cosmetic_block_returns_declaration_for_modifier_with_cells() -> None:
    # A `Doubler`/`Constant`-marked block with cells returns its `(kind, k)`
    # declaration alongside the modifier directives — the only branch that
    # produces one.
    decode, declaration = _decode_cosmetic_block(
        "doubler", {"name": "Doubler"}, [{"cells": [0]}], size=9
    )

    assert decode.modifier_directives == (ModifierDirective("R1C1", is_modifier=True),)
    assert declaration == ("doubler", None)


def test_decode_cosmetic_block_skips_declaration_for_an_empty_modifier() -> None:
    # An empty `Doubler` block marks no cell, so it contributes no
    # declaration — the same "no cells, no fact" rule an empty killer cage
    # block follows.
    decode, declaration = _decode_cosmetic_block(
        "doubler", {"name": "Doubler"}, [], size=9
    )

    assert decode == _CosmeticCageDecode()
    assert declaration is None


def test_decode_cosmetic_block_warns_and_returns_an_empty_decode_for_unnamed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # An unnamed block with cages warns (the loud-drop side effect lives in
    # the pure decode, not the gathering loop) and returns an empty decode
    # and no declaration.
    decode, declaration = _decode_cosmetic_block(
        "unnamed", {"type": 2001}, [{"value": "7", "cells": [0, 1]}], size=9
    )

    assert decode == _CosmeticCageDecode()
    assert declaration is None
    assert "unnamed cosmetic cage" in capsys.readouterr().err


def test_decode_cosmetic_block_returns_scell_values_with_no_declaration() -> None:
    decode, declaration = _decode_cosmetic_block(
        "s-cell", {"name": "S-cell"}, [{"value": "5", "cells": [0]}], size=9
    )

    assert decode.scell_values == {"R1C1": "5"}
    assert decode.has_scell_block is True
    assert declaration is None
