"""Duplicate detection via gh CLI and difflib fuzzy matching."""

import json
import subprocess
from difflib import SequenceMatcher
from os import getenv


def find_duplicates(title: str, body: str, issue_number: int | None = None) -> list[dict]:
    """Find existing issues that are potential duplicates.

    Returns list of dicts with keys: number, title, score, sorted by score descending.
    When issue_number is provided, the issue with that number is excluded from the
    candidate pool to avoid self-matching during triage.
    """
    max_duplicates = int(getenv("MAX_DUPLICATES", "10"))
    threshold = float(getenv("SIMILARITY_THRESHOLD", "0.6"))

    existing = _fetch_existing_issues()
    scored = []

    for issue in existing:
        if issue_number is not None and issue["number"] == issue_number:
            continue
        title_score = SequenceMatcher(None, title.lower(), issue["title"].lower()).ratio()
        body_score = 0.0
        if body and issue.get("body"):
            body_score = SequenceMatcher(None, body.lower(), issue["body"].lower()).ratio()

        combined = title_score * 0.6 + body_score * 0.4
        if combined >= threshold:
            scored.append(
                {
                    "number": issue["number"],
                    "title": issue["title"],
                    "score": round(combined, 3),
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max_duplicates]


def _fetch_existing_issues() -> list[dict]:
    """Fetch open issues via gh CLI."""
    result = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--json",
            "title,number,body,labels,state",
            "--limit",
            "100",
            "--state",
            "all",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        print(f"::warning::gh issue list failed: {result.stderr}")
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print("::warning::Failed to parse gh issue list output")
        return []
