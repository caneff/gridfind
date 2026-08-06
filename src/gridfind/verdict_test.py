import pytest

from gridfind.layers import UnknownLayerError
from gridfind.verdict import verdict


def assert_layer_newly_breaks(
    smaller: list[str], full: list[str], directives: str
) -> None:
    """The full stack newly breaks a state the smaller stack still allows.

    Both stacks see the *same* directives, given once here — the whole point:
    the two copies can no longer drift apart by hand and pass while testing
    nothing.
    """
    lenient = verdict(smaller, f"stack: {', '.join(smaller)}\n{directives}")
    assert lenient.kind != "broke"

    strict = verdict(full, f"stack: {', '.join(full)}\n{directives}")
    assert strict.kind == "broke"
    assert strict.witness is None


def test_verdict_found_returns_a_witness_consistent_with_the_given() -> None:
    result = verdict(["board"], "stack: board\ngiven R1C1 5\n")

    assert result.kind == "found"
    assert result.witness is not None
    assert result.witness["R1C1"] == 5
    assert len(result.witness) == 81


def test_verdict_broke_on_a_given_place_conflict() -> None:
    result = verdict(["board"], "stack: board\ngiven R1C1 5\nplace R1C1 6\n")

    assert result.kind == "broke"
    assert result.witness is None


def test_verdict_broke_on_a_candidate_excluding_the_given() -> None:
    result = verdict(["board"], "stack: board\ngiven R1C1 5\ncandidate R1C1 {1,2,3}\n")

    assert result.kind == "broke"
    assert result.witness is None


def test_verdict_unknown_when_the_budget_is_exhausted() -> None:
    result = verdict(["board"], "stack: board\ngiven R1C1 5\n", time_limit_s=0.0)

    assert result.kind == "unknown"
    assert result.witness is None


def test_verdict_rejects_a_stack_header_mismatch() -> None:
    with pytest.raises(ValueError, match="stack"):
        verdict(["board"], "stack: rows-distinct\ngiven R1C1 5\n")


def test_rows_distinct_breaks_a_row_repeat_that_board_alone_would_not() -> None:
    assert_layer_newly_breaks(
        ["board"],
        ["board", "rows-distinct"],
        "given R1C1 5\ngiven R1C2 5\n",
    )


def test_rows_distinct_found_when_no_row_repeats() -> None:
    result = verdict(
        ["board", "rows-distinct"],
        "stack: board, rows-distinct\ngiven R1C1 1\ngiven R1C2 2\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_line_count_distinct_breaks_when_a_row_already_exceeds_its_target() -> None:
    assert_layer_newly_breaks(
        ["board"],
        ["board", "line-count-distinct"],
        "given R2C1 1\ngiven R2C2 2\ngiven R2C3 3\n",
    )


def test_line_count_distinct_found_when_row_counts_are_satisfiable() -> None:
    result = verdict(
        ["board", "line-count-distinct"],
        "stack: board, line-count-distinct\ngiven R1C1 4\ngiven R1C2 4\n",
    )

    assert result.kind == "found"
    assert result.witness is not None
    assert len({result.witness[f"R1C{c}"] for c in range(1, 10)}) == 1


def test_cols_distinct_breaks_a_col_repeat_that_board_alone_would_not() -> None:
    assert_layer_newly_breaks(
        ["board"],
        ["board", "cols-distinct"],
        "given R1C1 5\ngiven R2C1 5\n",
    )


def test_cols_distinct_found_when_no_col_repeats() -> None:
    result = verdict(
        ["board", "cols-distinct"],
        "stack: board, cols-distinct\ngiven R1C1 1\ngiven R2C1 2\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_latin_square_broke_on_a_column_repeat_rows_distinct_alone_misses() -> None:
    assert_layer_newly_breaks(
        ["board", "rows-distinct"],
        ["board", "rows-distinct", "cols-distinct"],
        "given R1C1 5\ngiven R5C1 5\n",
    )


def test_latin_square_found_on_a_legal_partial() -> None:
    result = verdict(
        ["board", "rows-distinct", "cols-distinct"],
        "stack: board, rows-distinct, cols-distinct\n"
        "given R1C1 1\ngiven R1C2 2\ngiven R2C1 2\ngiven R2C2 1\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_stack_order_does_not_change_the_verdict() -> None:
    text = "stack: board, rows-distinct, cols-distinct\ngiven R1C1 5\ngiven R5C1 5\n"

    forward = verdict(["board", "rows-distinct", "cols-distinct"], text)
    reversed_order = verdict(["cols-distinct", "rows-distinct", "board"], text)

    assert forward.kind == reversed_order.kind == "broke"


def test_regions_distinct_breaks_a_box_repeat_rows_and_cols_distinct_miss() -> None:
    assert_layer_newly_breaks(
        ["board", "rows-distinct", "cols-distinct"],
        ["board", "rows-distinct", "cols-distinct", "regions-distinct"],
        "given R1C1 5\ngiven R2C2 5\n",
    )


def test_regions_distinct_found_when_no_box_repeats() -> None:
    stack = ["board", "rows-distinct", "cols-distinct", "regions-distinct"]
    text = f"stack: {', '.join(stack)}\ngiven R1C1 1\ngiven R4C4 2\n"

    result = verdict(stack, text)
    assert result.kind == "found"
    assert result.witness is not None


def test_classic_sudoku_preset_matches_the_explicit_layer_list() -> None:
    explicit_stack = ["board", "rows-distinct", "cols-distinct", "regions-distinct"]
    text = f"stack: {', '.join(explicit_stack)}\ngiven R1C1 5\ngiven R2C2 5\n"
    preset_text = "stack: classic-sudoku\ngiven R1C1 5\ngiven R2C2 5\n"

    explicit = verdict(explicit_stack, text)
    preset = verdict("classic-sudoku", preset_text)

    assert preset.kind == explicit.kind == "broke"


def test_classic_sudoku_preset_found_on_a_legal_partial() -> None:
    result = verdict(
        "classic-sudoku",
        "stack: classic-sudoku\ngiven R1C1 1\ngiven R4C4 2\n",
    )

    assert result.kind == "found"
    assert result.witness is not None


def test_verdict_rejects_an_unknown_preset_name() -> None:
    with pytest.raises(UnknownLayerError):
        verdict("not-a-real-preset", "stack: not-a-real-preset\n")


def test_regions_distinct_irregular_catches_a_repeat_classic_regions_miss() -> None:
    assert_layer_newly_breaks(
        ["board", "rows-distinct", "cols-distinct", "regions-distinct"],
        ["board", "rows-distinct", "cols-distinct", "regions-distinct-irregular"],
        "given R3C3 5\ngiven R2C4 5\n",
    )
