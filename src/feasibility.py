"""Feasibility and complexity analysis via LLM."""

import json
import subprocess

from llm import call_llm


def analyze_feasibility(title: str, body: str) -> dict:
    """Analyze issue feasibility and complexity via LLM.

    Returns dict with keys: complexity (low/medium/high), reasoning, estimated_effort.
    """
    context = _get_codebase_summary()
    system_prompt = (
        "You are an issue triage assistant. Analyze the feasibility and complexity "
        "of a GitHub issue. Respond with valid JSON only, no markdown.\n"
        "Fields: complexity (one of: low, medium, high), "
        "reasoning (one sentence), estimated_effort (one of: hours, days, weeks)."
    )
    user_prompt = (
        f"Codebase summary:\n{context}\n\n"
        f"Issue title: {title}\n"
        f"Issue body: {body}\n\n"
        "Analyze this issue's feasibility and complexity."
    )

    response = call_llm(system_prompt, user_prompt)
    return _parse_response(response)


def _get_codebase_summary() -> str:
    """Get a brief summary of the codebase structure via file listing."""
    result = subprocess.run(
        ["find", ".", "-type", "f", "-not", "-path", "./.git/*", "-not", "-path", "./.venv/*"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        files = result.stdout.strip().split("\n")[:50]
        return f"Repository files ({len(files)} shown):\n" + "\n".join(files)
    return "Could not list repository files."


def _parse_response(response: str) -> dict:
    """Parse LLM JSON response with fallback defaults."""
    try:
        data = json.loads(response)
        return {
            "complexity": data.get("complexity", "medium"),
            "reasoning": data.get("reasoning", ""),
            "estimated_effort": data.get("estimated_effort", "days"),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "complexity": "medium",
            "reasoning": "Failed to parse LLM response",
            "estimated_effort": "days",
        }
