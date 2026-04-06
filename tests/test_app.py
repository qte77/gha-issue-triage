"""Tests for app.py — event dispatch orchestrator."""

import json
from unittest.mock import patch

from src.app import main


def _write_event(tmp_path, event_name, action, issue_number=1, title="Test", body="body"):
    """Helper: write a GitHub event payload and set env vars."""
    payload = {
        "action": action,
        "issue": {"number": issue_number, "title": title, "body": body},
    }
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps(payload))
    return {
        "GITHUB_EVENT_NAME": event_name,
        "GITHUB_EVENT_PATH": str(event_file),
    }


@patch("src.app.apply_labels")
@patch(
    "src.app.analyze_feasibility",
    return_value={"complexity": "low", "reasoning": "", "estimated_effort": "hours"},
)
@patch(
    "src.app.score_relevance",
    return_value={"score": 8, "category": "bug", "irrelevant": False, "reasoning": ""},
)
@patch("src.app.find_duplicates", return_value=[])
def test_main_dispatches_opened_issue(mock_dup, mock_rel, mock_feas, mock_labels, tmp_path):
    """Opened issue triggers full pipeline and applies labels."""
    # Arrange
    env = _write_event(tmp_path, "issues", "opened")

    # Act
    with patch.dict("os.environ", env, clear=False):
        main()

    # Assert
    mock_dup.assert_called_once()
    mock_rel.assert_called_once()
    mock_feas.assert_called_once()
    mock_labels.assert_called_once_with(1, ["good-first-issue", "bug"])


@patch("src.app.apply_labels")
@patch("src.app.analyze_feasibility")
@patch("src.app.score_relevance")
@patch("src.app.find_duplicates")
def test_main_skips_non_issue_event(mock_dup, mock_rel, mock_feas, mock_labels, tmp_path):
    """Non-issue events are skipped without calling any triage functions."""
    # Arrange
    env = _write_event(tmp_path, "push", "")

    # Act
    with patch.dict("os.environ", env, clear=False):
        main()

    # Assert
    mock_dup.assert_not_called()
    mock_rel.assert_not_called()


@patch("src.app.apply_labels")
@patch("src.app.analyze_feasibility")
@patch("src.app.score_relevance")
@patch("src.app.find_duplicates")
def test_main_skips_closed_action(mock_dup, mock_rel, mock_feas, mock_labels, tmp_path):
    """Closed action is skipped."""
    # Arrange
    env = _write_event(tmp_path, "issues", "closed")

    # Act
    with patch.dict("os.environ", env, clear=False):
        main()

    # Assert
    mock_dup.assert_not_called()


@patch("src.app.apply_labels")
@patch(
    "src.app.analyze_feasibility",
    return_value={"complexity": "high", "reasoning": "", "estimated_effort": "weeks"},
)
@patch(
    "src.app.score_relevance",
    return_value={"score": 2, "category": "invalid", "irrelevant": True, "reasoning": ""},
)
@patch(
    "src.app.find_duplicates",
    return_value=[{"number": 5, "title": "Dup", "score": 0.85}],
)
def test_main_duplicate_and_irrelevant_labels(mock_dup, mock_rel, mock_feas, mock_labels, tmp_path):
    """Duplicate + irrelevant issue gets both labels."""
    # Arrange
    env = _write_event(tmp_path, "issues", "opened")

    # Act
    with patch.dict("os.environ", env, clear=False):
        main()

    # Assert
    mock_labels.assert_called_once()
    labels = mock_labels.call_args[0][1]
    assert "duplicate" in labels
    assert "invalid" in labels
