"""Score issue relevance against repo scope via LLM."""

import json
from pathlib import Path

from llm import call_llm


def score_relevance(title: str, body: str) -> dict:
    """Score how relevant an issue is to the repository scope.

    Returns dict with keys: score (1-10), category, irrelevant (bool), reasoning.
    """
    context = _load_repo_context()
    system_prompt = (
        "You are an issue triage assistant. Score the relevance of a GitHub issue "
        "to the repository scope. Respond with valid JSON only, no markdown.\n"
        "Fields: score (1-10), category (one of: bug, feature, enhancement, "
        "needs-discussion, invalid), irrelevant (bool, true if score <= 3), "
        "reasoning (one sentence)."
    )
    user_prompt = (
        f"Repository context:\n{context}\n\n"
        f"Issue title: {title}\n"
        f"Issue body: {body}\n\n"
        "Score this issue's relevance."
    )

    response = call_llm(system_prompt, user_prompt)
    return _parse_response(response)


def _load_repo_context() -> str:
    """Load README.md and CLAUDE.md if present for repo scope context."""
    parts = []
    for name in ("README.md", "CLAUDE.md"):
        path = Path(name)
        if path.exists():
            content = path.read_text(encoding="utf-8")[:2000]
            parts.append(f"--- {name} ---\n{content}")
    return "\n\n".join(parts) if parts else "No repository context files found."


def _parse_response(response: str) -> dict:
    """Parse LLM JSON response with fallback defaults."""
    try:
        data = json.loads(response)
        return {
            "score": int(data.get("score", 5)),
            "category": data.get("category", "needs-discussion"),
            "irrelevant": bool(data.get("irrelevant", False)),
            "reasoning": data.get("reasoning", ""),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "score": 5,
            "category": "needs-discussion",
            "irrelevant": False,
            "reasoning": "Failed to parse LLM response",
        }
