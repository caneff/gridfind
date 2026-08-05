import pytest

from gridfind.layers import UnknownLayerError
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


def test_cols_distinct_breaks_a_col_repeat_that_board_alone_would_not():
    text = "stack: board, cols-distinct\ngiven R1C1 5\ngiven R2C1 5\n"

    board_only = verdict(["board"], "stack: board\ngiven R1C1 5\ngiven R2C1 5\n")
    assert board_only.kind != "broke"

    result = verdict(["board", "cols-distinct"], text)
    assert result.kind == "broke"
    assert result.witness is None


def test_cols_distinct_found_when_no_col_repeats():
    result = verdict(
        ["board", "cols-distinct"],
        "stack: board, cols-distinct\ngiven R1C1 1\ngiven R2C1 2\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_latin_square_broke_on_a_column_repeat_rows_distinct_alone_misses():
    text = "stack: board, rows-distinct, cols-distinct\ngiven R1C1 5\ngiven R5C1 5\n"

    rows_only = verdict(
        ["board", "rows-distinct"],
        "stack: board, rows-distinct\ngiven R1C1 5\ngiven R5C1 5\n",
    )
    assert rows_only.kind != "broke"

    result = verdict(["board", "rows-distinct", "cols-distinct"], text)
    assert result.kind == "broke"
    assert result.witness is None


def test_latin_square_found_on_a_legal_partial():
    result = verdict(
        ["board", "rows-distinct", "cols-distinct"],
        "stack: board, rows-distinct, cols-distinct\n"
        "given R1C1 1\ngiven R1C2 2\ngiven R2C1 2\ngiven R2C2 1\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_stack_order_does_not_change_the_verdict():
    text = "stack: board, rows-distinct, cols-distinct\ngiven R1C1 5\ngiven R5C1 5\n"

    forward = verdict(["board", "rows-distinct", "cols-distinct"], text)
    reversed_order = verdict(["cols-distinct", "rows-distinct", "board"], text)

    assert forward.kind == reversed_order.kind == "broke"


def test_regions_distinct_breaks_a_box_repeat_rows_and_cols_distinct_would_miss():
    stack = ["board", "rows-distinct", "cols-distinct", "regions-distinct"]
    text = f"stack: {', '.join(stack)}\ngiven R1C1 5\ngiven R2C2 5\n"

    without_regions = verdict(
        ["board", "rows-distinct", "cols-distinct"],
        "stack: board, rows-distinct, cols-distinct\ngiven R1C1 5\ngiven R2C2 5\n",
    )
    assert without_regions.kind != "broke"

    result = verdict(stack, text)
    assert result.kind == "broke"
    assert result.witness is None


def test_regions_distinct_found_when_no_box_repeats():
    stack = ["board", "rows-distinct", "cols-distinct", "regions-distinct"]
    text = f"stack: {', '.join(stack)}\ngiven R1C1 1\ngiven R4C4 2\n"

    result = verdict(stack, text)
    assert result.kind == "found"
    assert result.witness is not None


def test_classic_sudoku_preset_matches_the_explicit_layer_list():
    explicit_stack = ["board", "rows-distinct", "cols-distinct", "regions-distinct"]
    text = f"stack: {', '.join(explicit_stack)}\ngiven R1C1 5\ngiven R2C2 5\n"
    preset_text = "stack: classic-sudoku\ngiven R1C1 5\ngiven R2C2 5\n"

    explicit = verdict(explicit_stack, text)
    preset = verdict("classic-sudoku", preset_text)

    assert preset.kind == explicit.kind == "broke"


def test_classic_sudoku_preset_found_on_a_legal_partial():
    result = verdict(
        "classic-sudoku",
        "stack: classic-sudoku\ngiven R1C1 1\ngiven R4C4 2\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_verdict_rejects_an_unknown_preset_name():
    with pytest.raises(UnknownLayerError):
        verdict("not-a-real-preset", "stack: not-a-real-preset\n")


def test_regions_distinct_irregular_catches_a_repeat_classic_regions_would_miss():
    text = (
        "stack: board, rows-distinct, cols-distinct, regions-distinct-irregular\n"
        "given R3C3 5\ngiven R2C4 5\n"
    )

    classic = verdict(
        ["board", "rows-distinct", "cols-distinct", "regions-distinct"],
        "stack: board, rows-distinct, cols-distinct, regions-distinct\n"
        "given R3C3 5\ngiven R2C4 5\n",
    )
    assert classic.kind != "broke"

    result = verdict(
        ["board", "rows-distinct", "cols-distinct", "regions-distinct-irregular"],
        text,
    )
    assert result.kind == "broke"
    assert result.witness is None
