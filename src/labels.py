"""Auto-label issues via gh CLI."""

import subprocess

VALID_LABELS = {
    "duplicate",
    "bug",
    "feature",
    "enhancement",
    "good-first-issue",
    "needs-discussion",
    "invalid",
}


def apply_labels(issue_number: int, labels: list[str]) -> bool:
    """Apply labels to an issue via gh CLI.

    Returns True if labels were applied successfully.
    """
    valid = [label for label in labels if label in VALID_LABELS]
    if not valid:
        print("No valid labels to apply")
        return False

    _ensure_labels_exist(valid)

    result = subprocess.run(
        ["gh", "issue", "edit", str(issue_number), "--add-label", ",".join(valid)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(f"::warning::Failed to apply labels: {result.stderr}")
        return False

    return True


def _ensure_labels_exist(labels: list[str]) -> None:
    """Create labels if they don't already exist."""
    for label in labels:
        subprocess.run(
            ["gh", "label", "create", label, "--force"],
            capture_output=True,
            text=True,
            check=False,
        )
