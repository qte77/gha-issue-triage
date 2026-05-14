"""Tests for labels.py — auto-labeling via gh CLI."""

from unittest.mock import MagicMock, patch

from src.labels import VALID_LABELS, _ensure_labels_exist, _get_current_labels, apply_labels


def _mk_run(stdout: str = "", returncode: int = 0, stderr: str = ""):
    """Build a CompletedProcess-like mock."""
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    m.stderr = stderr
    return m


def test_valid_labels_set():
    """VALID_LABELS contains expected labels."""
    assert "bug" in VALID_LABELS
    assert "duplicate" in VALID_LABELS
    assert "good-first-issue" in VALID_LABELS


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_adds_to_empty_issue(mock_ensure, mock_run):
    """First triage: no current labels → adds desired labels."""
    # Arrange: view returns empty, edit succeeds
    mock_run.side_effect = [_mk_run(stdout=""), _mk_run(returncode=0)]

    # Act
    result = apply_labels(42, ["bug", "feature"])

    # Assert
    assert result is True
    mock_ensure.assert_called_once_with(["bug", "feature"])
    assert mock_run.call_count == 2
    edit_cmd = mock_run.call_args_list[1][0][0]
    assert "--add-label" in edit_cmd
    assert "bug,feature" in edit_cmd
    assert "--remove-label" not in edit_cmd


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_removes_fossil(mock_ensure, mock_run):
    """Re-triage with reduced desired set removes the dropped label."""
    # Arrange: issue has bug + enhancement, desired is only bug
    mock_run.side_effect = [_mk_run(stdout="bug\nenhancement\n"), _mk_run(returncode=0)]

    # Act
    result = apply_labels(42, ["bug"])

    # Assert
    assert result is True
    assert mock_run.call_count == 2
    edit_cmd = mock_run.call_args_list[1][0][0]
    assert "--remove-label" in edit_cmd
    assert "enhancement" in edit_cmd
    assert "--add-label" not in edit_cmd
    mock_ensure.assert_not_called()


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_noop_when_in_sync(mock_ensure, mock_run):
    """When desired matches managed_current, no gh edit call is made."""
    # Arrange
    mock_run.side_effect = [_mk_run(stdout="bug\n")]

    # Act
    result = apply_labels(42, ["bug"])

    # Assert
    assert result is True
    mock_run.assert_called_once()  # only view, no edit
    mock_ensure.assert_not_called()


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_preserves_human_labels(mock_ensure, mock_run):
    """Labels outside VALID_LABELS are never touched by reconciliation."""
    # Arrange: human added 'help-wanted' (not in VALID_LABELS); desired matches managed
    mock_run.side_effect = [_mk_run(stdout="bug\nhelp-wanted\n")]

    # Act
    result = apply_labels(42, ["bug"])

    # Assert: bug already present, help-wanted untouched → no edit call
    assert result is True
    mock_run.assert_called_once()


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_add_and_remove_in_one_call(mock_ensure, mock_run):
    """A single gh edit invocation carries both --add-label and --remove-label."""
    # Arrange: had enhancement, now want bug
    mock_run.side_effect = [_mk_run(stdout="enhancement\n"), _mk_run(returncode=0)]

    # Act
    result = apply_labels(42, ["bug"])

    # Assert
    assert result is True
    edit_cmd = mock_run.call_args_list[1][0][0]
    assert "--add-label" in edit_cmd
    assert "bug" in edit_cmd
    assert "--remove-label" in edit_cmd
    assert "enhancement" in edit_cmd


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_filters_invalid(mock_ensure, mock_run):
    """Labels not in VALID_LABELS are filtered out of the desired set."""
    # Arrange
    mock_run.side_effect = [_mk_run(stdout=""), _mk_run(returncode=0)]

    # Act
    result = apply_labels(1, ["bug", "not-a-real-label"])

    # Assert
    assert result is True
    mock_ensure.assert_called_once_with(["bug"])


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_view_failure_falls_back_to_add_only(mock_ensure, mock_run):
    """If `gh issue view` fails, treat current labels as empty (fail-open add)."""
    # Arrange: view fails, edit succeeds
    mock_run.side_effect = [_mk_run(returncode=1, stderr="boom"), _mk_run(returncode=0)]

    # Act
    result = apply_labels(42, ["bug"])

    # Assert
    assert result is True
    edit_cmd = mock_run.call_args_list[1][0][0]
    assert "--add-label" in edit_cmd
    assert "bug" in edit_cmd
    assert "--remove-label" not in edit_cmd


@patch("src.labels.subprocess.run")
@patch("src.labels._ensure_labels_exist")
def test_apply_labels_gh_edit_failure(mock_ensure, mock_run):
    """Returns False when gh edit fails."""
    # Arrange
    mock_run.side_effect = [_mk_run(stdout=""), _mk_run(returncode=1, stderr="error")]

    # Act
    result = apply_labels(1, ["bug"])

    # Assert
    assert result is False


@patch("src.labels.subprocess.run")
def test_get_current_labels_returns_set(mock_run):
    """Parses gh issue view output into a set."""
    # Arrange
    mock_run.return_value = _mk_run(stdout="bug\nduplicate\n")

    # Act
    result = _get_current_labels(42)

    # Assert
    assert result == {"bug", "duplicate"}


@patch("src.labels.subprocess.run")
def test_get_current_labels_empty_on_failure(mock_run):
    """Returns empty set when gh fails (fail-open)."""
    # Arrange
    mock_run.return_value = _mk_run(returncode=1, stderr="not found")

    # Act
    result = _get_current_labels(42)

    # Assert
    assert result == set()


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
