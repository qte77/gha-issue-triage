"""Auto-label issues via gh CLI with reconciliation against the managed scope."""

import json
import subprocess

from _gh_errors import raise_or_degrade_gh_error

# Default descriptions, set when the bot creates a label or finds it with an
# empty description. A description a repo owner already set is never overwritten.
LABEL_DESCRIPTIONS = {
    "bug": "Something isn't working",
    "documentation": "Improvements or additions to documentation",
    "duplicate": "This issue or pull request already exists",
    "enhancement": "Improvement to existing functionality",
    "feature": "New capability / feature request",
    "good first issue": "Good for newcomers",
    "invalid": "This doesn't seem right",
    "needs discussion": "Requires further discussion before action",
}

VALID_LABELS = set(LABEL_DESCRIPTIONS)

# Labels the bot previously managed but no longer applies. Reconciliation
# treats these as managed (so they appear in `managed_current`) but they're
# excluded from `desired`, which means existing attachments are removed on
# the next triage of any affected issue. Migrate the label name on the repo
# itself via `gh label edit OLD --name NEW` to preserve the underlying
# identifier; this set ensures stale attachments don't linger when only
# the desired set changed.
DEPRECATED_LABELS = {
    "good-first-issue",
    "needs-discussion",
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
    managed_current = current & (VALID_LABELS | DEPRECATED_LABELS)

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
        raise_or_degrade_gh_error(result.stderr, "Failed to reconcile labels")
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


def _get_repo_label_descriptions() -> dict[str, str] | None:
    """Map the repo's label names to their descriptions. None on failure (fail-open)."""
    result = subprocess.run(
        ["gh", "label", "list", "--json", "name,description", "--limit", "1000"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"::warning::Failed to list repo labels: {result.stderr}")
        return None
    try:
        return {item["name"]: item.get("description") or "" for item in json.loads(result.stdout)}
    except (json.JSONDecodeError, KeyError, TypeError):
        print("::warning::Failed to parse gh label list output")
        return None


def _ensure_labels_exist(labels: list[str]) -> None:
    """Create missing labels with a default description; backfill empty descriptions.

    Idempotent: a label that already has a description is left untouched.
    """
    existing = _get_repo_label_descriptions() or {}
    for label in labels:
        description = LABEL_DESCRIPTIONS.get(label, "")
        if label not in existing:
            action = "create"
        elif not existing[label] and description:
            action = "edit"
        else:
            continue
        cmd = ["gh", "label", action, label]
        if description:
            cmd.extend(["--description", description])
        subprocess.run(cmd, capture_output=True, text=True, check=False)
