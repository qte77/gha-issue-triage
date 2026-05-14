"""Main entry point for AI issue triage action."""

import json
import sys
from os import getenv

from comment import post_summary
from duplicates import find_duplicates
from feasibility import analyze_feasibility
from labels import apply_labels
from relevance import score_relevance


def main() -> None:
    """Read GitHub event payload and dispatch to triage pipeline."""
    event_name = getenv("GITHUB_EVENT_NAME", "")
    event_path = getenv("GITHUB_EVENT_PATH", "")

    if event_name != "issues":
        print(f"Skipping non-issue event: {event_name}")
        return

    if not event_path:
        print("::error::GITHUB_EVENT_PATH not set")
        sys.exit(1)

    with open(event_path) as f:
        event = json.load(f)

    action = event.get("action", "")
    if action not in ("opened", "edited", "labeled"):
        print(f"Skipping issue action: {action}")
        return

    issue = event.get("issue", {})
    issue_number = issue.get("number")
    title = issue.get("title", "")
    body = issue.get("body", "")

    if not issue_number:
        print("::error::Could not read issue number from event payload")
        sys.exit(1)

    print(f"Triaging issue #{issue_number}: {title}")

    labels: list[str] = []

    # Step 1: Duplicate detection
    duplicates = find_duplicates(title, body, issue_number=issue_number)
    if duplicates:
        top = duplicates[0]
        print(f"Potential duplicate: #{top['number']} (score: {top['score']:.2f})")
        labels.append("duplicate")

    # Step 2: Relevance scoring
    relevance = score_relevance(title, body)
    print(f"Relevance score: {relevance['score']}")
    if relevance.get("irrelevant"):
        labels.append("invalid")

    # Step 3: Feasibility analysis
    feasibility = analyze_feasibility(title, body)
    print(f"Feasibility: {feasibility['feasibility']} / Complexity: {feasibility['complexity']}")
    if feasibility["feasibility"] == "yes" and feasibility["complexity"] == "low":
        labels.append("good-first-issue")

    # Step 4: Category labeling — suppressed when issue is out-of-scope
    category = relevance.get("category", "")
    if not relevance.get("irrelevant") and category in ("bug", "feature", "enhancement", "needs-discussion"):
        labels.append(category)

    # Step 5: Apply labels
    if labels:
        apply_labels(issue_number, labels)
        print(f"Applied labels: {labels}")
    else:
        print("No labels to apply")

    # Step 6: Post sticky analysis summary comment
    post_summary(issue_number, duplicates, relevance, feasibility)


if __name__ == "__main__":
    main()
