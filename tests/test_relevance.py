"""Tests for relevance.py — LLM-based relevance scoring."""

import json
from unittest.mock import patch

from src.relevance import _load_repo_context, _parse_response, score_relevance


def test_parse_response_valid_json():
    """Parses valid LLM JSON response."""
    # Arrange
    response = json.dumps(
        {
            "score": 8,
            "category": "bug",
            "irrelevant": False,
            "reasoning": "Clearly a bug report",
        }
    )

    # Act
    result = _parse_response(response)

    # Assert
    assert result["score"] == 8
    assert result["category"] == "bug"
    assert result["irrelevant"] is False


def test_parse_response_invalid_json():
    """Returns defaults on malformed response."""
    # Act
    result = _parse_response("not json at all")

    # Assert
    assert result["score"] == 5
    assert result["category"] == "needs-discussion"
    assert result["irrelevant"] is False


def test_parse_response_missing_fields():
    """Returns defaults for missing fields."""
    # Arrange
    response = json.dumps({"score": 3})

    # Act
    result = _parse_response(response)

    # Assert
    assert result["score"] == 3
    assert result["category"] == "needs-discussion"


def test_load_repo_context_no_files(tmp_path):
    """Returns fallback message when no context files exist."""
    # Act
    with patch("src.relevance.Path") as mock_path:
        mock_path.return_value.exists.return_value = False
        result = _load_repo_context()

    # Assert
    assert "No repository context" in result


@patch("src.relevance.call_llm")
def test_score_relevance_returns_parsed_result(mock_llm):
    """score_relevance calls LLM and returns parsed dict."""
    # Arrange
    mock_llm.return_value = json.dumps(
        {
            "score": 7,
            "category": "feature",
            "irrelevant": False,
            "reasoning": "Relevant feature request",
        }
    )

    # Act
    with patch("src.relevance._load_repo_context", return_value="repo context"):
        result = score_relevance("Add feature X", "Details about X")

    # Assert
    assert result["score"] == 7
    assert result["category"] == "feature"
    mock_llm.assert_called_once()
