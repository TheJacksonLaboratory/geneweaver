"""Test the prompt_for_list_selection function."""

import typing
from unittest.mock import Mock

import pytest
from geneweaver.client.utils.cli.prompt.list import prompt_for_list_selection


@pytest.mark.parametrize(
    ("list_type", "example_input"),
    [
        (str, ["a", "b", "c"]),
        (int, [1, 2, 3]),
        (str | int, ["a", 1, "b", 2]),
        (typing.Any, ["a", 1, "b", 2]),
        (str, ["a", "b", "c"] * 1000),
        (int, [1, 2, 3] * 1000),
    ],
)
def test_prompt_for_list_selection(list_type, example_input, monkeypatch):
    """Test the prompt_for_list_selection function."""
    example_input.append("")
    mock_prompt = Mock(side_effect=example_input)
    monkeypatch.setattr("geneweaver.client.utils.cli.prompt.list.typer.prompt", mock_prompt)
    result = prompt_for_list_selection(list[list_type])
    if list_type is int:
        assert result == [int(x) for x in example_input[:-1]]
        assert all(isinstance(x, int) for x in result)
    elif list_type is str:
        assert result == [str(i) for i in example_input[:-1]]
        assert all(isinstance(x, str) for x in result)
    else:
        assert result == example_input[:-1]


@pytest.mark.parametrize(
    "field_type",
    [
        dict[str, str],
        dict[str, int],
        str | int,
        typing.Any,
        tuple[str, int],
        typing.Callable,
        str | None,
        int | None,
        typing.BinaryIO,
        typing.IO[str],
        typing.IO[int],
        typing.IO[typing.Any],
        typing.IO[str | int],
    ],
)
def test_prompt_for_list_selection__invalid_field_type(field_type):
    """Test the prompt_for_list_selection function with invalid input."""
    with pytest.raises(TypeError):
        prompt_for_list_selection(field_type)
