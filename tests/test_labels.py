"""Tests for labels.py — auto-labeling via gh CLI."""

from unittest.mock import patch

from src.labels import VALID_LABELS, _ensure_labels_exist, apply_labels


def test_valid_labels_set():
    """VALID_LABELS contains expected labels."""
    # Assert
    assert "bug" in VALID_LABELS
    assert "duplicate" in VALID_LABELS
    assert "good-first-issue" in VALID_LABELS


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_success(mock_ensure, mock_run):
    """Applies valid labels via gh CLI."""
    # Arrange
    mock_run.return_value.returncode = 0

    # Act
    result = apply_labels(42, ["bug", "feature"])

    # Assert
    assert result is True
    mock_ensure.assert_called_once_with(["bug", "feature"])
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "gh" in cmd
    assert "42" in cmd


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_filters_invalid(mock_ensure, mock_run):
    """Filters out labels not in VALID_LABELS."""
    # Arrange
    mock_run.return_value.returncode = 0

    # Act
    result = apply_labels(1, ["bug", "not-a-real-label"])

    # Assert
    assert result is True
    mock_ensure.assert_called_once_with(["bug"])


def test_apply_labels_no_valid_labels():
    """Returns False when no valid labels to apply."""
    # Act
    result = apply_labels(1, ["totally-fake"])

    # Assert
    assert result is False


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_gh_failure(mock_ensure, mock_run):
    """Returns False when gh CLI fails."""
    # Arrange
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "error"

    # Act
    result = apply_labels(1, ["bug"])

    # Assert
    assert result is False


@patch("src.labels.subprocess.run")
def test_ensure_labels_exist_creates_labels(mock_run):
    """Calls gh label create for each label."""
    # Arrange
    mock_run.return_value.returncode = 0

    # Act
    _ensure_labels_exist(["bug", "feature"])

    # Assert
    assert mock_run.call_count == 2
    calls = mock_run.call_args_list
    assert "bug" in calls[0][0][0]
    assert "feature" in calls[1][0][0]
