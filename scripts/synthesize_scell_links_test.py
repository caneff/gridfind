"""Per-case behaviour tests for the synthesized S-cell corpus.

Each covering case is asserted on two axes: the *directive kind* the link
decodes to (so a `found` fixture can't secretly be a plain classic puzzle that
exercises no S-cell path), and the front-door verdict/exit `cli.main` returns.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any, cast

import pytest
import synthesize_scell_links as syn

from gridfind import cli
from gridfind.puzzle import ModifierDirective, WorkingState
from gridfind.s_directives import (
    BareSCell,
    HalfSCell,
    SCellMarkRestriction,
    SCellPin,
    SingletonPin,
)
from gridfind.sudokumaker import link_to_document, link_to_puzzle
from gridfind.verdict import verdict


def _front_door(link: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Drive `cli.main` with a bare link; return (exit code, first stdout line,
    stderr)."""
    code = cli.main([link], io.StringIO())
    captured = capsys.readouterr()
    return code, captured.out.split("\n")[0], captured.err


def _state(link: str) -> WorkingState:
    _, state = link_to_puzzle(link)
    return state


def test_found_pin_declares_one_scell_and_the_solver_discovers_the_rest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_pin()
    pins = [d for d in _state(link).s_directives if isinstance(d, SCellPin)]
    assert len(pins) == 1
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_found_pin_decodes_the_default_zero_to_n_domain() -> None:
    # No fixture declares minDigit; the named S-cell block alone widens the
    # decoded domain to 0…N (ADR-0014).
    puzzle, _ = link_to_puzzle(syn.found_pin())
    assert puzzle.board.values == range(puzzle.board.size + 1)


def test_found_half_decodes_a_half_scell_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_half()
    assert any(isinstance(d, HalfSCell) for d in _state(link).s_directives)
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_found_bare_decodes_a_bare_scell_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_bare()
    assert any(isinstance(d, BareSCell) for d in _state(link).s_directives)
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_found_stray_marks_adds_a_restriction_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_stray_marks()
    directives = _state(link).s_directives
    assert any(isinstance(d, SCellMarkRestriction) for d in directives)
    assert any(isinstance(d, SCellPin) for d in directives)
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_broke_consistency_restriction_omitting_the_pair_reads_broke(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.broke_consistency()
    assert any(isinstance(d, SCellMarkRestriction) for d in _state(link).s_directives)
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (1, "broke")


def test_broke_settled_position_leaves_the_extra_digit_unplaceable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.broke_settled()
    assert any(isinstance(d, SingletonPin) for d in _state(link).s_directives)
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (1, "broke")


def test_broke_caged_cell_with_its_own_value_collides_and_reads_broke(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.broke_caged_value()
    directives = _state(link).s_directives
    assert any(isinstance(d, SCellPin) for d in directives)
    assert any(isinstance(d, SingletonPin) for d in directives)
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (1, "broke")


def test_malformed_out_of_domain_value_exits_two_as_a_malformed_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _, err = _front_door(syn.malformed_out_of_domain(), capsys)
    assert code == 2
    assert "malformed puzzle document" in err


def test_found_schrodinger_6x6_declares_one_scell_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_schrodinger_6x6()
    pins = [d for d in _state(link).s_directives if isinstance(d, SCellPin)]
    assert len(pins) == 1
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_found_schrodinger_6x6_is_a_partial_puzzle_with_working_state(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_schrodinger_6x6()
    # A partial puzzle, not a blank board: pre-set center marks (working state
    # the solver narrows from) alongside a plain given or two, still found.
    assert _state(link).candidates
    assert _given_count(link) >= 1
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def _has_live_doubler(state: WorkingState) -> bool:
    return any(
        isinstance(d, ModifierDirective) and d.is_modifier
        for d in state.modifier_directives
    )


def test_found_doubler_migration_keeps_a_live_doubler_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_doubler_4x4()
    assert _has_live_doubler(_state(link))
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_broke_doubler_migration_keeps_a_live_doubler_and_reads_broke(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.broke_doubler_4x4()
    assert _has_live_doubler(_state(link))
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (1, "broke")


def _caged_2001_blocks(link: str) -> list[dict[str, Any]]:
    """The enabled `type 2001` blocks the emitted document carries that hold at
    least one cage — the blocks a `cage`/`group-sum` rule can ride."""
    puzzle = cast("dict[str, Any]", link_to_document(link)["puzzle"])
    blocks = cast("list[dict[str, Any]]", puzzle["constraints"])
    return [
        b
        for b in blocks
        if b.get("type") == 2001 and not b.get("disabled") and b.get("cages")
    ]


@pytest.mark.parametrize(
    "builder",
    [syn.found_doubler_4x4, syn.broke_doubler_4x4, syn.found_doubled_scell_17cage_4x4],
    ids=lambda v: v.__name__ if callable(v) else str(v),
)
def test_composition_sum_rides_a_named_sum_cage(builder: Callable[[], str]) -> None:
    # The doubler / S-cell + sum composition carries its sum on a `Sum`-named
    # cosmetic cage: no cage-bearing cosmetic block is left unnamed, so no live
    # rule rides an unnamed cage the coming warn-drop would silence.
    blocks = _caged_2001_blocks(builder())
    assert blocks, "expected at least one cage-bearing cosmetic block"
    for block in blocks:
        assert block.get("name"), f"unnamed cage-bearing cosmetic block: {block}"


def test_sumless_cage_stays_a_bare_named_cage_and_reads_broke(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A `Sum`-named cage with an empty value emits a live no-repeats `cage`
    # (and no `group-sum`), and that no-repeats rule alone breaks the board.
    # Naming it moves the rule off the unnamed cosmetic path without changing
    # the verdict.
    link = syn.broke_cosmetic_cage_sumless_4x4()
    puzzle, _ = link_to_puzzle(link)
    assert any(c.type == "cage" for c in puzzle.constraints)
    assert all(c.type != "group-sum" for c in puzzle.constraints)
    assert all(b.get("name") for b in _caged_2001_blocks(link))
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (1, "broke")


def test_numeric_cage_graduates_to_a_group_sum_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The mirror of the sumless case above: a `Sum`-named cage with a numeric
    # value graduates to a real killer sum, emitting both the no-repeats
    # `cage` and a `group-sum` carrying that value (ADR-0008).
    link = syn.found_cosmetic_cage_4x4()
    puzzle, _ = link_to_puzzle(link)
    assert any(c.type == "cage" for c in puzzle.constraints)
    group_sums = [c for c in puzzle.constraints if c.type == "group-sum"]
    assert [c.params["sum"] for c in group_sums] == [3]
    assert all(b.get("name") for b in _caged_2001_blocks(link))
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_unrecognized_named_cage_warns_and_drops_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # "Foobar" matches no entry in naming._NAME_REGISTRY, so the cage carries
    # no rule (ADR-0012): it's warn-dropped rather than honored as a killer
    # cage, which would otherwise break on the repeated digit 3 shared by
    # cells 0 and 6. The verdict is computed from the given solution alone.
    link = syn.found_cosmetic_cage_unrecognized_4x4()
    puzzle, _ = link_to_puzzle(link)
    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)
    code, first, err = _front_door(link, capsys)
    assert (code, first) == (0, "found")
    assert "Foobar" in err


def test_unnamed_cage_warns_and_drops_and_reads_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # An absent `name` (no `Foobar`, no `Sum`) is the other input the
    # warn-drop treats the same as an unrecognized name: no rule rides the
    # block, so the given solution alone decides the verdict.
    link = syn.found_cosmetic_cage_unnamed_4x4()
    puzzle, _ = link_to_puzzle(link)
    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)
    code, first, err = _front_door(link, capsys)
    assert (code, first) == (0, "found")
    assert "unnamed" in err


@pytest.mark.parametrize(
    "builder",
    [syn.broke_cosmetic_cage_unnamed_4x4, syn.broke_cosmetic_cage_unrecognized_4x4],
    ids=lambda v: v.__name__ if callable(v) else str(v),
)
def test_dropped_cage_reads_broke_on_an_unrelated_row_repeat(
    builder: Callable[[], str], capsys: pytest.CaptureFixture[str]
) -> None:
    # Both the unnamed and the unrecognized-named cage warn-drop the same
    # way; a plain row-uniqueness violation elsewhere still reads broke
    # either way, proving the drop reaches the broke side too, not just found.
    link = builder()
    puzzle, _ = link_to_puzzle(link)
    assert all(c.type not in ("cage", "group-sum") for c in puzzle.constraints)
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (1, "broke")


def test_found_doubled_scell_17cage_witness_carries_a_doubled_scell_at_r1c3(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The doubled-S-cell motivating link: a 17-sum cage closes only if R1C3 is
    # a doubled S-cell holding {3, 4} — 2·(3+4) + 2 + 1 — on domain 0…4. The
    # witness must carry R1C3 as both two-digit (an S-cell) and `doubler`, so
    # the discovery is a genuine doubled-S-cell solve, not either channel alone.
    link = syn.found_doubled_scell_17cage_4x4()
    puzzle, state = link_to_puzzle(link)
    result = verdict(puzzle, state)
    assert result.kind == "found"
    assert result.witness is not None
    assert len(result.witness.assignment["R1C3"]) == 2
    assert result.witness.modifiers["R1C3"] == "doubler"
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


def test_found_doubled_scell_17cage_witness_never_doubles_a_digit_twice() -> None:
    # A doubled S-cell doubles *both* its digits, so no two discovered
    # doublers may share any doubled digit. Read the invariant
    # off the returned witness — each doubler contributes the digits its cell
    # displays (both for an S-cell), and those contributions must be disjoint.
    link = syn.found_doubled_scell_17cage_4x4()
    puzzle, state = link_to_puzzle(link)
    result = verdict(puzzle, state)
    assert result.kind == "found"
    assert result.witness is not None
    doubled: list[int] = []
    for address in result.witness.modifiers:
        doubled.extend(result.witness.assignment[address])
    assert len(doubled) == len(set(doubled))


def _given_count(link: str) -> int:
    """Ordinary givens the emitted document pins — cells flagged `given`."""
    puzzle = cast("dict[str, Any]", link_to_document(link)["puzzle"])
    cells = cast("list[dict[str, Any]]", puzzle["cells"])
    return sum(1 for c in cells if c.get("given"))


# A Schrödinger fixture is a puzzle, not an answer key: the ordinary cells are
# left blank for the solver. The only cell a fixture may pin is a break that
# *is* a given — `broke_settled` settles one position as a plain digit,
# `broke_caged_value` gives a caged cell its own digit — so those carry exactly
# one. Every other fixture, found or mark-broken, pins nothing.
@pytest.mark.parametrize(
    ("builder", "givens"),
    [
        (syn.found_pin, 0),
        (syn.found_half, 0),
        (syn.found_bare, 0),
        (syn.found_stray_marks, 0),
        (syn.found_schrodinger_6x6, 2),
        (syn.broke_consistency, 0),
        (syn.broke_settled, 1),
        (syn.broke_caged_value, 1),
        (syn.malformed_out_of_domain, 0),
    ],
    ids=lambda v: v.__name__ if callable(v) else str(v),
)
def test_schrodinger_fixture_pins_only_its_load_bearing_cell(
    builder: Callable[[], str], givens: int
) -> None:
    assert _given_count(builder()) == givens
