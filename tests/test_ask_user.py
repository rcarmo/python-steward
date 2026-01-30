"""Tests for ask_user tool."""

import json

import pytest

from steward.tools.ask_user import set_input_callback
from steward.tools.ask_user import tool_ask_user as tool_handler


@pytest.fixture
def mock_input():
    """Fixture to mock user input."""
    responses = []

    def callback(question, choices, allow_freeform):
        if responses:
            return responses.pop(0)
        return "mock response"

    set_input_callback(callback)
    yield responses
    set_input_callback(None)


def test_ask_user_basic(mock_input):
    """Test basic ask_user functionality."""
    mock_input.append("yes")
    result = tool_handler(question="Continue?")

    assert result["id"] == "ask_user"
    data = json.loads(result["output"])
    assert data["question"] == "Continue?"
    assert data["response"] == "yes"


def test_ask_user_with_choices(mock_input):
    """Test ask_user with choices."""
    mock_input.append("Option A")
    result = tool_handler(
        question="Pick one",
        choices=["Option A", "Option B", "Option C"],
    )

    data = json.loads(result["output"])
    assert data["response"] == "Option A"
    assert data["choices_offered"] == ["Option A", "Option B", "Option C"]


def test_ask_user_requires_question():
    """Test that ask_user requires question."""
    with pytest.raises(ValueError, match="question"):
        tool_handler(question="")


def test_ask_user_requires_nonempty_question():
    """Test that ask_user requires non-empty question."""
    with pytest.raises(ValueError, match="question"):
        tool_handler(question="   ")


def test_ask_user_strips_question(mock_input):
    """Test that question is stripped."""
    mock_input.append("answer")
    result = tool_handler(question="  What?  ")

    data = json.loads(result["output"])
    assert data["question"] == "What?"
