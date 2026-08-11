import pytest

from gridfind import grid_text


@pytest.mark.parametrize(
    ("content", "token"),
    [
        pytest.param((5,), "5", id="singleton"),
        pytest.param((0, 5), "{0 5}", id="s-cell-pair"),
    ],
)
def test_format_cell_and_parse_cell_round_trip(
    content: tuple[int, ...], token: str
) -> None:
    assert grid_text.format_cell(content) == token

    match = grid_text.CELL_PATTERN.fullmatch(token)
    assert match is not None
    assert grid_text.parse_cell(match) == content


def test_line_count_interleaves_one_more_border_line_than_cell_lines() -> None:
    # 4 cell lines need 5 border lines bracketing/between them.
    assert grid_text.line_count(4) == 9


def test_cell_line_indices_are_every_other_line_starting_at_one() -> None:
    assert list(grid_text.cell_line_indices(4)) == [1, 3, 5, 7]
