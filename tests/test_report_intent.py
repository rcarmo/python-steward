"""Tests for report_intent tool."""
import pytest

from steward.tools.report_intent import get_current_intent, tool_report_intent as tool_handler


def test_report_intent_stores_intent():
    """Test that report_intent stores the intent."""
    result = tool_handler(intent="Exploring codebase")
    assert result["id"] == "report_intent"
    assert "Exploring codebase" in result["output"]
    assert get_current_intent() == "Exploring codebase"


def test_report_intent_updates_intent():
    """Test that report_intent updates the intent."""
    tool_handler(intent="First intent")
    assert get_current_intent() == "First intent"

    tool_handler(intent="Second intent")
    assert get_current_intent() == "Second intent"


def test_report_intent_requires_intent():
    """Test that report_intent requires intent."""
    # Calling without intent should return error
    result = tool_handler(intent="")
    assert result.get("error") is True
    assert "required" in result["output"].lower()


def test_report_intent_requires_nonempty():
    """Test that report_intent requires non-empty intent."""
    result = tool_handler(intent="   ")
    assert result.get("error") is True
    assert "required" in result["output"].lower()


def test_report_intent_strips_whitespace():
    """Test that report_intent strips whitespace."""
    tool_handler(intent="  Testing  ")
    assert get_current_intent() == "Testing"
