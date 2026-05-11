"""Tests for comment.py — idempotent sticky summary comment."""

import json
from unittest.mock import MagicMock, patch

from src.comment import MARKER, post_summary

RELEVANCE = {
    "score": 7,
    "category": "enhancement",
    "irrelevant": False,
    "reasoning": "Adds caller-side flexibility.",
}
FEASIBILITY = {
    "complexity": "low",
    "reasoning": "One-line config change.",
    "estimated_effort": "hours",
}
DUPLICATES = [{"number": 5, "title": "Existing", "score": 0.82}]


def _ok(stdout: str = "") -> MagicMock:
    """A subprocess.run return-value mock with returncode 0 and given stdout."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    return m


def _fail(stderr: str = "boom") -> MagicMock:
    """A subprocess.run return-value mock that simulates failure."""
    m = MagicMock()
    m.returncode = 1
    m.stderr = stderr
    return m


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment.subprocess.run")
def test_post_summary_creates_new_when_no_marker(mock_run):
    """No existing marker comment → posts a new one via gh issue comment."""
    # Arrange: list comments returns empty array, then create succeeds
    mock_run.side_effect = [_ok(stdout="[]"), _ok()]

    # Act
    result = post_summary(7, DUPLICATES, RELEVANCE, FEASIBILITY)

    # Assert
    assert result is True
    assert mock_run.call_count == 2
    create_call = mock_run.call_args_list[1]
    cmd = create_call.args[0]
    assert cmd[:4] == ["gh", "issue", "comment", "7"]
    body = cmd[cmd.index("--body") + 1]
    assert MARKER in body
    assert "#5" in body
    assert RELEVANCE["reasoning"] in body
    assert FEASIBILITY["reasoning"] in body


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment.subprocess.run")
def test_post_summary_updates_existing_marker_comment(mock_run):
    """Existing marker comment → PATCHes that comment, no new create call."""
    # Arrange: list returns one comment containing the marker; update succeeds
    comments = [{"id": 999, "body": f"{MARKER}\nold body"}]
    mock_run.side_effect = [_ok(stdout=json.dumps(comments)), _ok()]

    # Act
    result = post_summary(7, [], RELEVANCE, FEASIBILITY)

    # Assert
    assert result is True
    assert mock_run.call_count == 2
    update_call = mock_run.call_args_list[1]
    cmd = update_call.args[0]
    assert cmd[:4] == ["gh", "api", "-X", "PATCH"]
    assert "/repos/qte77/gha-issue-triage/issues/comments/999" in cmd
    # No second issue-comment create call
    assert all("gh" not in c.args[0] or c.args[0][:3] != ["gh", "issue", "comment"]
               for c in mock_run.call_args_list)


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment.subprocess.run")
def test_post_summary_returns_false_on_create_failure(mock_run, capsys):
    """Create-comment failure → returns False and prints a warning, never raises."""
    # Arrange: list returns empty, create fails
    mock_run.side_effect = [_ok(stdout="[]"), _fail(stderr="rate limit")]

    # Act
    result = post_summary(7, [], RELEVANCE, FEASIBILITY)

    # Assert
    assert result is False
    assert "::warning::Failed to create summary comment" in capsys.readouterr().out


@patch.dict("os.environ", {}, clear=True)
@patch("src.comment.subprocess.run")
def test_post_summary_skips_when_repo_env_missing(mock_run, capsys):
    """No GITHUB_REPOSITORY set → no subprocess calls; warn and return False."""
    # Act
    result = post_summary(7, [], RELEVANCE, FEASIBILITY)

    # Assert
    assert result is False
    assert mock_run.call_count == 0
    assert "GITHUB_REPOSITORY not set" in capsys.readouterr().out
