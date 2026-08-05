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


def test_rows_distinct_breaks_a_row_repeat_that_board_alone_would_not():
    text = "stack: board, rows-distinct\ngiven R1C1 5\ngiven R1C2 5\n"

    board_only = verdict(["board"], "stack: board\ngiven R1C1 5\ngiven R1C2 5\n")
    assert board_only.kind != "broke"

    result = verdict(["board", "rows-distinct"], text)
    assert result.kind == "broke"
    assert result.witness is None


def test_rows_distinct_found_when_no_row_repeats():
    result = verdict(
        ["board", "rows-distinct"],
        "stack: board, rows-distinct\ngiven R1C1 1\ngiven R1C2 2\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_line_count_distinct_breaks_when_a_row_already_exceeds_its_target():
    text = (
        "stack: board, line-count-distinct\ngiven R2C1 1\ngiven R2C2 2\ngiven R2C3 3\n"
    )

    board_only = verdict(
        ["board"], "stack: board\ngiven R2C1 1\ngiven R2C2 2\ngiven R2C3 3\n"
    )
    assert board_only.kind != "broke"

    result = verdict(["board", "line-count-distinct"], text)
    assert result.kind == "broke"
    assert result.witness is None


def test_line_count_distinct_found_when_row_counts_are_satisfiable():
    result = verdict(
        ["board", "line-count-distinct"],
        "stack: board, line-count-distinct\ngiven R1C1 4\ngiven R1C2 4\n",
    )

    assert result.kind == "found"
    assert result.witness is not None
    assert len({result.witness[f"R1C{c}"] for c in range(1, 10)}) == 1
