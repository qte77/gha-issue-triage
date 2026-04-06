"""Tests for feasibility.py — complexity analysis via LLM."""

import json
from unittest.mock import patch

from src.feasibility import _get_codebase_summary, _parse_response, analyze_feasibility


def test_parse_response_valid_json():
    """Parses valid LLM JSON response."""
    # Arrange
    response = json.dumps(
        {
            "complexity": "low",
            "reasoning": "Simple text change",
            "estimated_effort": "hours",
        }
    )

    # Act
    result = _parse_response(response)

    # Assert
    assert result["complexity"] == "low"
    assert result["estimated_effort"] == "hours"


def test_parse_response_invalid_json():
    """Returns defaults on malformed response."""
    # Act
    result = _parse_response("broken json {{{")

    # Assert
    assert result["complexity"] == "medium"
    assert result["estimated_effort"] == "days"


def test_parse_response_missing_fields():
    """Returns defaults for missing fields."""
    # Arrange
    response = json.dumps({"complexity": "high"})

    # Act
    result = _parse_response(response)

    # Assert
    assert result["complexity"] == "high"
    assert result["estimated_effort"] == "days"


@patch("src.feasibility.subprocess.run")
def test_get_codebase_summary_success(mock_run):
    """Returns file listing on success."""
    # Arrange
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "./src/app.py\n./README.md\n"

    # Act
    result = _get_codebase_summary()

    # Assert
    assert "app.py" in result
    assert "Repository files" in result


@patch("src.feasibility.subprocess.run")
def test_get_codebase_summary_failure(mock_run):
    """Returns fallback message when find fails."""
    # Arrange
    mock_run.return_value.returncode = 1

    # Act
    result = _get_codebase_summary()

    # Assert
    assert "Could not list" in result


@patch("src.feasibility.call_llm")
@patch("src.feasibility._get_codebase_summary", return_value="file list")
def test_analyze_feasibility_returns_parsed_result(mock_summary, mock_llm):
    """analyze_feasibility calls LLM and returns parsed dict."""
    # Arrange
    mock_llm.return_value = json.dumps(
        {
            "complexity": "high",
            "reasoning": "Requires major refactoring",
            "estimated_effort": "weeks",
        }
    )

    # Act
    result = analyze_feasibility("Rewrite auth system", "Complete overhaul needed")

    # Assert
    assert result["complexity"] == "high"
    assert result["estimated_effort"] == "weeks"
    mock_llm.assert_called_once()
