"""Idempotent sticky summary comment via gh CLI."""

import json
import subprocess
from os import getenv

MARKER = "<!-- gha-issue-triage:summary -->"


def post_summary(
    issue_number: int,
    duplicates: list[dict],
    relevance: dict,
    feasibility: dict,
) -> bool:
    """Post or update the AI triage summary comment on the issue.

    Idempotent: finds an existing bot comment via a hidden HTML marker and edits
    it instead of posting a duplicate. Returns True on success, False on any
    subprocess failure (warning printed, never raises — label application has
    already succeeded by the time this is called).
    """
    body = _build_body(duplicates, relevance, feasibility)
    repo = getenv("GITHUB_REPOSITORY", "")
    if not repo:
        print("::warning::GITHUB_REPOSITORY not set; skipping summary comment")
        return False

    existing_id = _find_existing_comment_id(repo, issue_number)
    if existing_id is not None:
        return _update_comment(repo, existing_id, body)
    return _create_comment(issue_number, body)


def _build_body(duplicates: list[dict], relevance: dict, feasibility: dict) -> str:
    """Render the summary markdown body, including the hidden marker."""
    lines = [MARKER, "### AI triage summary", ""]
    if duplicates:
        top = duplicates[0]
        lines.append(f"- **Duplicate of:** #{top['number']} (similarity {top['score']:.2f})")

    score = relevance.get("score", "?")
    category = relevance.get("category", "")
    rel_reason = relevance.get("reasoning", "")
    rel_line = f"- **Relevance:** {score}/10 — `{category}`"
    if rel_reason:
        rel_line += f" — {rel_reason}"
    lines.append(rel_line)

    feasible = feasibility.get("feasibility", "yes")
    complexity = feasibility.get("complexity", "")
    feas_reason = feasibility.get("reasoning", "")
    effort = feasibility.get("estimated_effort", "")
    feas_line = f"- **Feasibility:** `{feasible}`"
    if feasible == "no" and feas_reason:
        feas_line += f" — {feas_reason}"
    lines.append(feas_line)
    if feasible == "yes":
        cx_line = f"- **Complexity:** `{complexity}`"
        if feas_reason:
            cx_line += f" — {feas_reason}"
        if effort:
            cx_line += f" (~{effort})"
        lines.append(cx_line)

    lines.append("")
    lines.append("_Auto-generated. Re-runs when the issue is opened, edited, or labelled._")
    return "\n".join(lines)


def _find_existing_comment_id(repo: str, issue_number: int) -> int | None:
    """Return the id of an existing bot comment containing the marker, or None."""
    result = subprocess.run(
        ["gh", "api", f"/repos/{repo}/issues/{issue_number}/comments"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"::warning::gh api list comments failed: {result.stderr}")
        return None
    try:
        comments = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("::warning::Failed to parse comments JSON")
        return None
    for c in comments:
        if MARKER in c.get("body", ""):
            return c["id"]
    return None


def _create_comment(issue_number: int, body: str) -> bool:
    """Create a new comment on the issue."""
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--body", body],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"::warning::Failed to create summary comment: {result.stderr}")
        return False
    return True


def _update_comment(repo: str, comment_id: int, body: str) -> bool:
    """Patch the body of an existing comment."""
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "PATCH",
            f"/repos/{repo}/issues/comments/{comment_id}",
            "-f",
            f"body={body}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"::warning::Failed to update summary comment: {result.stderr}")
        return False
    return True
