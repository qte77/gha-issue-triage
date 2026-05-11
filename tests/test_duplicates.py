"""Tests for duplicates.py — duplicate detection via fuzzy matching."""

import json
from unittest.mock import patch

from src.duplicates import _fetch_existing_issues, find_duplicates

SAMPLE_ISSUES = [
    {
        "number": 1,
        "title": "Fix login bug",
        "body": "Login fails on Safari",
        "labels": [],
        "state": "open",
    },
    {
        "number": 2,
        "title": "Add dark mode",
        "body": "Support dark theme",
        "labels": [],
        "state": "open",
    },
    {
        "number": 3,
        "title": "Update docs",
        "body": "README is outdated",
        "labels": [],
        "state": "open",
    },
]


@patch("src.duplicates.subprocess.run")
def test_fetch_existing_issues_success(mock_run):
    """Fetches and parses issues from gh CLI."""
    # Arrange
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps(SAMPLE_ISSUES)

    # Act
    result = _fetch_existing_issues()

    # Assert
    assert len(result) == 3
    assert result[0]["number"] == 1


@patch("src.duplicates.subprocess.run")
def test_fetch_existing_issues_failure(mock_run):
    """Returns empty list when gh CLI fails."""
    # Arrange
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "auth error"

    # Act
    result = _fetch_existing_issues()

    # Assert
    assert result == []


@patch("src.duplicates._fetch_existing_issues", return_value=SAMPLE_ISSUES)
def test_find_duplicates_exact_match(mock_fetch):
    """Exact title match scores above threshold."""
    # Act
    with patch.dict("os.environ", {"SIMILARITY_THRESHOLD": "0.6", "MAX_DUPLICATES": "10"}):
        result = find_duplicates("Fix login bug", "Login fails on Safari")

    # Assert
    assert len(result) >= 1
    assert result[0]["number"] == 1
    assert result[0]["score"] >= 0.9


@patch("src.duplicates._fetch_existing_issues", return_value=SAMPLE_ISSUES)
def test_find_duplicates_no_match(mock_fetch):
    """Unrelated issue returns no duplicates."""
    # Act
    with patch.dict("os.environ", {"SIMILARITY_THRESHOLD": "0.6", "MAX_DUPLICATES": "10"}):
        result = find_duplicates("Implement GraphQL API", "New API layer for queries")

    # Assert
    assert result == []


@patch("src.duplicates._fetch_existing_issues", return_value=SAMPLE_ISSUES)
def test_find_duplicates_respects_threshold(mock_fetch):
    """High threshold filters out partial matches."""
    # Act
    with patch.dict("os.environ", {"SIMILARITY_THRESHOLD": "0.99", "MAX_DUPLICATES": "10"}):
        result = find_duplicates("Fix login issue", "Login is broken")

    # Assert
    assert result == []


@patch("src.duplicates._fetch_existing_issues", return_value=SAMPLE_ISSUES)
def test_find_duplicates_respects_max(mock_fetch):
    """MAX_DUPLICATES limits results."""
    # Act
    with patch.dict("os.environ", {"SIMILARITY_THRESHOLD": "0.0", "MAX_DUPLICATES": "2"}):
        result = find_duplicates("anything", "anything")

    # Assert
    assert len(result) <= 2


@patch("src.duplicates._fetch_existing_issues", return_value=SAMPLE_ISSUES)
def test_find_duplicates_excludes_self(mock_fetch):
    """Passing issue_number excludes that issue from the candidate pool."""
    # Act
    with patch.dict("os.environ", {"SIMILARITY_THRESHOLD": "0.6", "MAX_DUPLICATES": "10"}):
        result = find_duplicates("Fix login bug", "Login fails on Safari", issue_number=1)

    # Assert
    assert all(item["number"] != 1 for item in result)
