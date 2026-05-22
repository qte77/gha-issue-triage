"""Tests for comment.py — idempotent sticky summary comment."""

import json
from unittest.mock import MagicMock, patch

from src.comment import MARKER, post_failure, post_summary
from src.errors import TriageFailure

FAILURE = TriageFailure(
    class_name="HTTPError",
    status=401,
    summary="GitHub API returned 401 Unauthorized",
    fix_markdown="Check that `GH_TOKEN` is set and has `issues: write` permission.",
)

RELEVANCE = {
    "score": 7,
    "category": "enhancement",
    "irrelevant": False,
    "reasoning": "Adds caller-side flexibility.",
}
FEASIBILITY = {
    "feasibility": "yes",
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
    # Regression: the feasibility line keeps its closing paren.
    assert f"(~{FEASIBILITY['estimated_effort']})" in body


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
    assert all(
        "gh" not in c.args[0] or c.args[0][:3] != ["gh", "issue", "comment"]
        for c in mock_run.call_args_list
    )


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


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment.subprocess.run")
def test_post_summary_omits_optional_fields_cleanly(mock_run):
    """Empty reasoning/effort produce a clean body — no trailing ' — ' or '(~)'."""
    # Arrange
    minimal_rel = {"score": 5, "category": "bug", "irrelevant": False, "reasoning": ""}
    minimal_feas = {
        "feasibility": "yes",
        "complexity": "low",
        "reasoning": "",
        "estimated_effort": "",
    }
    mock_run.side_effect = [_ok(stdout="[]"), _ok()]

    # Act
    result = post_summary(7, [], minimal_rel, minimal_feas)

    # Assert
    assert result is True
    body = mock_run.call_args_list[1].args[0][-1]
    assert "- **Relevance:** 5/10 — `bug`\n" in body
    assert "- **Feasibility:** `yes`\n" in body
    assert "- **Complexity:** `low`\n" in body
    assert "(~)" not in body
    assert " — \n" not in body


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment.subprocess.run")
def test_post_summary_feasibility_no_omits_complexity_line(mock_run):
    """When feasibility=no, render Feasibility with reasoning, omit Complexity line."""
    # Arrange
    infeasible = {
        "feasibility": "no",
        "complexity": "high",
        "reasoning": "Violates known physics.",
        "estimated_effort": "weeks",
    }
    mock_run.side_effect = [_ok(stdout="[]"), _ok()]

    # Act
    result = post_summary(7, [], RELEVANCE, infeasible)

    # Assert
    assert result is True
    body = mock_run.call_args_list[1].args[0][-1]
    assert "- **Feasibility:** `no` — Violates known physics." in body
    assert "Complexity" not in body
    assert "(~weeks)" not in body


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


# ---------------------------------------------------------------------------
# C2 — post_failure body format
# ---------------------------------------------------------------------------


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment.subprocess.run")
def test_post_failure_body_format(mock_run):
    """post_failure body contains MARKER, summary, and fix_markdown."""
    # Arrange: no existing comment, create succeeds
    mock_run.side_effect = [_ok(stdout="[]"), _ok()]

    result = post_failure(7, FAILURE)

    assert result is True
    create_call = mock_run.call_args_list[1]
    cmd = create_call.args[0]
    body = cmd[cmd.index("--body") + 1]
    assert MARKER in body
    assert FAILURE.summary in body
    assert FAILURE.fix_markdown in body


# ---------------------------------------------------------------------------
# C3 — post_failure creates new when no marker
# ---------------------------------------------------------------------------


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment._create_comment")
@patch("src.comment._find_existing_comment_id")
def test_post_failure_creates_new_when_no_marker(mock_find, mock_create):
    """_find_existing_comment_id returns None → _create_comment is called."""
    mock_find.return_value = None
    mock_create.return_value = True

    result = post_failure(7, FAILURE)

    assert result is True
    mock_create.assert_called_once()
    call_args = mock_create.call_args
    assert call_args.args[0] == 7  # issue_number


# ---------------------------------------------------------------------------
# C4 — post_failure updates existing marker comment
# ---------------------------------------------------------------------------


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment._update_comment")
@patch("src.comment._find_existing_comment_id")
def test_post_failure_updates_existing_marker(mock_find, mock_update):
    """_find_existing_comment_id returns 42 → _update_comment called with id 42."""
    mock_find.return_value = 42
    mock_update.return_value = True

    result = post_failure(7, FAILURE)

    assert result is True
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args.args[1] == 42  # comment_id


# ---------------------------------------------------------------------------
# C5 — regression pin: post_summary overwrites post_failure via shared marker
# ---------------------------------------------------------------------------


@patch.dict("os.environ", {"GITHUB_REPOSITORY": "qte77/gha-issue-triage"}, clear=False)
@patch("src.comment.subprocess.run")
def test_post_summary_overwrites_post_failure_via_marker(mock_run):
    """post_summary after post_failure updates the same comment (single marker)."""
    # Step 1: post_failure creates comment (list returns empty, create succeeds)
    mock_run.side_effect = [_ok(stdout="[]"), _ok()]
    post_failure(7, FAILURE)

    # Step 2: post_summary sees the marker → updates comment id=77
    existing = [{"id": 77, "body": f"{MARKER}\nfailure body"}]
    mock_run.side_effect = [_ok(stdout=json.dumps(existing)), _ok()]

    result = post_summary(7, [], RELEVANCE, FEASIBILITY)

    assert result is True
    # post_failure consumed calls 0+1; post_summary calls are at 2+3
    update_call = mock_run.call_args_list[3]
    cmd = update_call.args[0]
    # Must PATCH, not create a new comment
    assert cmd[:4] == ["gh", "api", "-X", "PATCH"]
    assert "/repos/qte77/gha-issue-triage/issues/comments/77" in cmd
    # Updated body must contain the summary marker (not failure content)
    body_part = [a for a in cmd if isinstance(a, str) and a.startswith("body=")]
    assert body_part, "Expected body= field in PATCH command"
    assert MARKER in body_part[0]
