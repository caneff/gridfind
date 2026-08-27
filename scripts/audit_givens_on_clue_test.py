"""Behavior tests for the givens-on-the-clue audit."""

from __future__ import annotations

from pathlib import Path

from audit_givens_on_clue import (
    EXEMPTIONS,
    build_report,
    constraint_cells,
    format_report,
    link_hits,
    puzzle_hits,
)

from gridfind.puzzle import Board, Constraint, Given, Puzzle

_LINKS_DIR = Path(__file__).resolve().parents[1] / "src" / "gridfind" / "links"


def test_constraint_cells_reads_the_tested_types_own_key() -> None:
    assert constraint_cells(Constraint("cage", {"cells": ["R1C1"]})) == ["R1C1"]
    assert constraint_cells(Constraint("line", {"path": ["R1C1", "R1C2"]})) == [
        "R1C1",
        "R1C2",
    ]


def test_constraint_cells_ignores_types_outside_the_rule() -> None:
    # Row/column/box/region uniqueness is explicitly not "the constraint
    # under test" (spec #723) and carries no cells param anyway.
    assert constraint_cells(Constraint("rows-distinct")) is None
    assert constraint_cells(Constraint("regions-distinct")) is None


def test_constraint_cells_ignores_negative_space_pairs() -> None:
    # A kropki/XV negative-space pair is the implicit default rule over every
    # *other* adjacent pair, not a drawn clue (edge_clues.py's `negate` flag).
    negated = Constraint(
        "pair-difference", {"cells": ["R1C1", "R1C2"], "diff": 1, "negate": True}
    )
    assert constraint_cells(negated) is None


def test_puzzle_hits_flags_a_given_on_a_constraint_cell() -> None:
    puzzle = Puzzle(
        board=Board(size=4),
        constraints=(Constraint("cage", {"cells": ["R1C1", "R1C2"]}),),
        givens=(Given("R1C1", 3),),
    )
    assert puzzle_hits(puzzle) == ["cage@R1C1"]


def test_puzzle_hits_passes_a_given_off_the_constraint_cells() -> None:
    puzzle = Puzzle(
        board=Board(size=4),
        constraints=(Constraint("cage", {"cells": ["R1C1", "R1C2"]}),),
        givens=(Given("R1C3", 3),),
    )
    assert puzzle_hits(puzzle) == []


def test_puzzle_hits_ignores_givens_off_any_tested_constraint() -> None:
    # A given is fine anywhere row/col/box/region touches — only the ten
    # clue-carrying types in `_TESTED_TYPES` gate a hit.
    puzzle = Puzzle(
        board=Board(size=4),
        constraints=(Constraint("rows-distinct"),),
        givens=(Given("R1C1", 3),),
    )
    assert puzzle_hits(puzzle) == []


def test_format_report_honors_an_exemption() -> None:
    exempt_stem = next(iter(EXEMPTIONS))
    report = {exempt_stem: ["cage@R1C1"], "found-not-exempt-4x4": ["cage@R2C2"]}
    text = format_report(report)
    assert "1 flagged link(s):" in text
    assert "found-not-exempt-4x4" in text
    assert "1 exempted link(s):" in text
    assert exempt_stem in text
    assert EXEMPTIONS[exempt_stem] in text


def test_format_report_clean_bill_when_nothing_flagged() -> None:
    exempt_stem = next(iter(EXEMPTIONS))
    text = format_report({exempt_stem: ["cage@R1C1"]})
    assert "No unexempted hits." in text


def test_link_hits_decodes_through_link_to_puzzle() -> None:
    link = (_LINKS_DIR / "broke-indexing-row-4x4.txt").read_text().strip()
    assert any(hit.startswith("indexing@") for hit in link_hits(link))


def test_build_report_wires_the_real_corpus() -> None:
    # Sanity that the decode wiring works end to end: a known offender hits,
    # keyed by its own constraint type. The indexing flags are explicitly
    # left unactioned (spec #723's "Further Notes"), so this stem stays a
    # stable offender — unlike the line-relation batch, whose givens never
    # sit on the clued line, so it never trips this audit.
    report = build_report(_LINKS_DIR)
    assert any(hit.startswith("indexing@") for hit in report["broke-indexing-row-4x4"])


def test_exemptions_name_real_corpus_links_with_a_reason() -> None:
    # Every exemption is a human ruling on a real link (spec #723 dec 3), not
    # a stem that doesn't exist.
    for stem, reason in EXEMPTIONS.items():
        assert (_LINKS_DIR / f"{stem}.txt").is_file()
        assert reason.strip()


def test_kropki_negative_six_are_exempted_not_flagged() -> None:
    # Each fixture's verdict turns on an unmarked negative pair, not the
    # marked dot the audit flags, so all six carry a ruling: a real corpus
    # link, with a real hit (the marked dot the audit would otherwise flag),
    # exempted with its own reason. `format_report`'s flagged/exempted split
    # on `EXEMPTIONS` membership is covered by
    # test_format_report_honors_an_exemption; this test only proves these six
    # stems are wired into that split, not the split's logic itself.
    stems = {
        "found-kropki-negative-4x4",
        "broke-kropki-negative-4x4",
        "found-kropki-negative-doubler-6x6",
        "broke-kropki-negative-doubler-6x6",
        "found-black-kropki-negative-4x4",
        "broke-black-kropki-negative-4x4",
    }
    report = build_report(_LINKS_DIR)
    for stem in stems:
        assert report[stem]
        assert stem in EXEMPTIONS
