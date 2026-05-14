"""Auto-label issues via gh CLI with reconciliation against the managed scope."""

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
    """Reconcile managed labels on an issue.

    Computes the diff between the desired set and the issue's current
    *managed* labels (those in VALID_LABELS), then applies additions and
    removals in a single gh call. Labels outside VALID_LABELS are left
    untouched — they may have been applied by a human reviewer.

    Returns True if the issue is in sync after the call (or already was).
    """
    desired = {label for label in labels if label in VALID_LABELS}
    current = _get_current_labels(issue_number)
    managed_current = current & VALID_LABELS

    to_add = desired - managed_current
    to_remove = managed_current - desired

    if not to_add and not to_remove:
        print("Labels already in sync, no-op")
        return True

    if to_add:
        _ensure_labels_exist(sorted(to_add))

    cmd = ["gh", "issue", "edit", str(issue_number)]
    if to_add:
        cmd.extend(["--add-label", ",".join(sorted(to_add))])
    if to_remove:
        cmd.extend(["--remove-label", ",".join(sorted(to_remove))])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        print(f"::warning::Failed to reconcile labels: {result.stderr}")
        return False

    return True


def _get_current_labels(issue_number: int) -> set[str]:
    """Read the issue's current labels. Empty set on failure (fail-open)."""
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number), "--json", "labels", "-q", ".labels[].name"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"::warning::Failed to read current labels: {result.stderr}")
        return set()
    return {line for line in result.stdout.splitlines() if line}


def _ensure_labels_exist(labels: list[str]) -> None:
    """Create labels if they don't already exist."""
    for label in labels:
        subprocess.run(
            ["gh", "label", "create", label, "--force"],
            capture_output=True,
            text=True,
            check=False,
        )
