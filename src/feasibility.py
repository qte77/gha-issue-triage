"""Feasibility and complexity analysis via LLM.

Two orthogonal judgements are produced per issue:

- ``feasibility`` (``yes`` / ``no``): can this be built at all?
  ``no`` means fundamentally impossible — out-of-physics, out-of-scope of
  software, or otherwise not implementable regardless of effort
  (e.g. "build a faster-than-light drive").
- ``complexity`` (``low`` / ``medium`` / ``high``): if ``feasibility`` is
  ``yes``, how hard is the implementation? Drives the ``good-first-issue``
  label when ``low``. Has no meaning when ``feasibility`` is ``no``.

``feasibility`` is distinct from ``relevance.irrelevant`` — that flag is
about scope (does this belong in *this* repo?); ``feasibility`` is about
whether the requested thing is implementable at all.
"""

import json
import subprocess

from llm import call_llm


def analyze_feasibility(title: str, body: str) -> dict:
    """Analyze issue feasibility and complexity via LLM.

    Returns dict with keys: feasibility (yes/no), complexity (low/medium/high),
    reasoning, estimated_effort. When feasibility is "no", complexity and
    estimated_effort are not meaningful (default to "high" / "weeks").
    """
    context = _get_codebase_summary()
    system_prompt = (
        "You are an issue triage assistant. Analyze a GitHub issue along two "
        "orthogonal axes. Respond with valid JSON only, no markdown.\n"
        "Fields:\n"
        "- feasibility: 'yes' if the requested thing can be built at all in any "
        "software project; 'no' if it is fundamentally impossible "
        "(out-of-physics, out-of-scope of software).\n"
        "- complexity: one of low, medium, high — implementation difficulty "
        "if feasibility is 'yes' (ignored otherwise).\n"
        "- reasoning: one sentence covering both axes.\n"
        "- estimated_effort: one of hours, days, weeks (ignored if feasibility is 'no')."
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
    """Parse LLM JSON response with fallback defaults.

    On parse failure, defaults to feasibility='yes' (don't bias toward
    'impossible') with medium complexity.
    """
    try:
        data = json.loads(response)
        feasibility = data.get("feasibility", "yes")
        if feasibility not in ("yes", "no"):
            feasibility = "yes"
        return {
            "feasibility": feasibility,
            "complexity": data.get("complexity", "medium"),
            "reasoning": data.get("reasoning", ""),
            "estimated_effort": data.get("estimated_effort", "days"),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "feasibility": "yes",
            "complexity": "medium",
            "reasoning": "Failed to parse LLM response",
            "estimated_effort": "days",
        }
