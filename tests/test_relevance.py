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
    assert result["category"] == "needs discussion"
    assert result["irrelevant"] is False


def test_parse_response_missing_fields():
    """Returns defaults for missing fields."""
    # Arrange
    response = json.dumps({"score": 3})

    # Act
    result = _parse_response(response)

    # Assert
    assert result["score"] == 3
    assert result["category"] == "needs discussion"


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


def test_parse_response_unknown_category_falls_back():
    """A category outside the fixed list is replaced, so model text never passes through."""
    # Act
    result = _parse_response(json.dumps({"score": 8, "category": "## PROBE **x**"}))

    # Assert
    assert result["category"] == "needs discussion"


def test_load_repo_context_reads_agents_md_without_claude_md(tmp_path, monkeypatch):
    """Falls back to AGENTS.md when the repo has no CLAUDE.md."""
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("Scope: agent research only.", encoding="utf-8")

    # Act
    result = _load_repo_context()

    # Assert
    assert "--- AGENTS.md ---\nScope: agent research only." in result


def test_load_repo_context_follows_claude_md_import(tmp_path, monkeypatch):
    """Reads AGENTS.md too when CLAUDE.md imports it with an @AGENTS.md line."""
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# Instructions\n\n@AGENTS.md\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Scope: agent research only.", encoding="utf-8")

    # Act
    result = _load_repo_context()

    # Assert
    assert "--- CLAUDE.md ---" in result
    assert "--- AGENTS.md ---\nScope: agent research only." in result


def test_load_repo_context_skips_agents_md_when_claude_md_stands_alone(tmp_path, monkeypatch):
    """A CLAUDE.md that doesn't import AGENTS.md is the only instructions file read."""
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("Scope: Claude rules.", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Other agents' rules.", encoding="utf-8")

    # Act
    result = _load_repo_context()

    # Assert
    assert "Scope: Claude rules." in result
    assert "AGENTS.md" not in result
