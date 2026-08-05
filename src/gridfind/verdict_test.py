import pytest

from gridfind.verdict import verdict


def test_verdict_found_returns_a_witness_consistent_with_the_given():
    result = verdict(["board"], "stack: board\ngiven R1C1 5\n")

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == 5
    assert len(result.witness) == 81


def test_verdict_broke_on_a_given_place_conflict():
    result = verdict(["board"], "stack: board\ngiven R1C1 5\nplace R1C1 6\n")

    assert result.kind == "broke"
    assert result.witness is None


def test_verdict_broke_on_a_candidate_excluding_the_given():
    result = verdict(["board"], "stack: board\ngiven R1C1 5\ncandidate R1C1 {1,2,3}\n")

    assert result.kind == "broke"
    assert result.witness is None


def test_verdict_unknown_when_the_budget_is_exhausted():
    result = verdict(["board"], "stack: board\ngiven R1C1 5\n", time_limit_s=0.0)

    assert result.kind == "unknown"
    assert result.witness is None


def test_verdict_rejects_a_stack_header_mismatch():
    with pytest.raises(ValueError, match="stack"):
        verdict(["board"], "stack: rows-distinct\ngiven R1C1 5\n")
