"""Behavior tests for the eval-link coverage audit."""

from __future__ import annotations

from pathlib import Path

from audit_link_coverage import (
    build_coverage,
    feature_universe,
    find_holes,
    link_features,
)

_LINKS_DIR = Path(__file__).resolve().parents[1] / "src" / "gridfind" / "links"


def test_universe_tracks_registry_and_cage_kinds() -> None:
    universe = feature_universe()
    assert "anti-king" in universe
    assert "white-kropki" in universe
    # Each cosmetic-cage marker kind is its own row, including `constant` now
    # that it decodes (ADR-0016).
    assert "cage:doubler" in universe
    assert "cage:s-cell" in universe
    assert "cage:constant" in universe


def test_link_features_reads_types_and_cage_kind() -> None:
    payload = {
        "constraints": [
            {"type": 12},
            {"type": 2001, "name": "Doubler"},
        ]
    }
    features = link_features(payload)
    assert "anti-king" in features
    assert "cosmetic-cage" in features
    assert "cage:doubler" in features


def test_link_features_skips_disabled() -> None:
    payload = {"constraints": [{"type": 12, "disabled": True}]}
    assert "anti-king" not in link_features(payload)


def test_find_holes_flags_missing_side() -> None:
    coverage = {
        "thermo": {"found": 2, "broke": 1},
        "white-kropki": {"found": 1, "broke": 0},
        "cage:unnamed": {"found": 0, "broke": 0},
    }
    holes = find_holes(coverage)
    assert not any("thermo" in h for h in holes)
    assert any("white-kropki" in h for h in holes)
    assert any("cage:unnamed" in h for h in holes)


def test_build_coverage_wires_real_corpus() -> None:
    coverage = build_coverage(_LINKS_DIR)
    # Sanity that the decode wiring works end to end: thermo has a found and a
    # broke link in the corpus today.
    assert coverage["thermo"]["found"] >= 1
    assert coverage["thermo"]["broke"] >= 1
