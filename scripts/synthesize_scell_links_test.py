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
from gridfind.puzzle import (
    BareSCell,
    HalfSCell,
    ModifierDirective,
    SCellMarkRestriction,
    SCellPin,
    SingletonPin,
    WorkingState,
)
from gridfind.sudokumaker import decode_document, decode_link


def _front_door(link: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Drive `cli.main` with a bare link; return (exit code, first stdout line,
    stderr)."""
    code = cli.main([link], io.StringIO())
    captured = capsys.readouterr()
    return code, captured.out.split("\n")[0], captured.err


def _state(link: str) -> WorkingState:
    _, state = decode_link(link)
    return state


def test_found_pin_declares_one_scell_and_the_solver_discovers_the_rest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    link = syn.found_pin()
    pins = [d for d in _state(link).s_directives if isinstance(d, SCellPin)]
    # Exactly one S-cell is declared; a 4x4 Schrödinger reads found only if the
    # solver discovers the other three, so found here is a real solve.
    assert len(pins) == 1
    code, first, _ = _front_door(link, capsys)
    assert (code, first) == (0, "found")


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


def test_invalid_out_of_domain_value_exits_two_as_a_malformed_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, _, err = _front_door(syn.invalid_out_of_domain(), capsys)
    assert code == 2
    assert "invalid puzzle document" in err


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


def _given_count(link: str) -> int:
    """Ordinary givens the emitted document pins — cells flagged `given`."""
    puzzle = cast("dict[str, Any]", decode_document(link)["puzzle"])
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
        (syn.invalid_out_of_domain, 0),
    ],
    ids=lambda v: v.__name__ if callable(v) else str(v),
)
def test_schrodinger_fixture_pins_only_its_load_bearing_cell(
    builder: Callable[[], str], givens: int
) -> None:
    assert _given_count(builder()) == givens


@pytest.mark.parametrize("name", sorted(syn.CORPUS), ids=sorted(syn.CORPUS))
def test_committed_corpus_file_matches_its_synthesizer(name: str) -> None:
    """The committed corpus is built in code, never hand-authored: each file is
    exactly its synthesizer's output. A hand-edit (or a stale regenerate) turns
    this red."""
    path = syn.LINKS_DIR / f"{name}.txt"
    assert path.read_text() == syn.CORPUS[name]() + "\n"
