"""Shadow-mode calibration: ask the triage's decision-shaped questions through
the shared `qte77/.github` `decide()` gate, alongside the existing LLM triage.

Shadow only: this module never sets labels and never changes the fixed-list
values rendered by the existing relevance/feasibility analysis -- it only
appends a separate, clearly-labelled section to the sticky comment (see
`comment.py`) so the decide() probabilities can be collected on real issues
before any threshold is used to gate behavior.

`decide()` itself never raises for a backend/network failure (each affected
question comes back banded "escalate" instead -- see its own docstring at
`qte77/.github:actions/decide/decide.py`). It *can* raise for a malformed
*call* (unknown backend, a clef model outside its allow-list, duplicate
question names) -- that would be our own bug, not a runtime condition, but
`run_shadow()` still never lets it (or a loader failure) propagate: this
boundary is wrap-degrade (see docs/architecture.md) because collecting
calibration data must never be able to break the actual triage pipeline.

`decide.py` is loaded at runtime via `importlib`, not vendored -- action.yaml
checks out `qte77/.github` at a pinned SHA into `DECIDE_MODULE_PATH` only when
`decide-shadow` is enabled.
"""

import importlib.util
import math
from pathlib import Path
from typing import Any

import config
from relevance import CATEGORIES as _RELEVANCE_CATEGORIES
from relevance import _load_repo_context

# Mirrors feasibility.py's own inline fixed lists (not re-exported there as
# constants) -- kept local rather than refactoring that module for this.
_COMPLEXITY_LEVELS = ("low", "medium", "high")
_EFFORT_LEVELS = ("hours", "days", "weeks")

_PREDICATE_NAMES = ("relevance_relevant", "feasibility_feasible")
_SCORE_NAMES = ("relevance_score",)

# Closed vocabulary per question -- any value decide() returns outside this
# set is discarded (-> None) rather than rendered, same discipline as
# relevance.py/feasibility.py's own `_parse_response` (#122): a backend answer
# for "choice"/"score" is forwarded by decide() unvalidated, and issue text
# can steer a model's free-form reply.
_CLOSED_SETS: dict[str, tuple[str, ...]] = {
    "relevance_category": _RELEVANCE_CATEGORIES,
    "relevance_score": tuple(str(n) for n in range(1, 11)),
    "feasibility_complexity": _COMPLEXITY_LEVELS,
    "feasibility_effort": _EFFORT_LEVELS,
}

_QUESTION_NAMES = (
    "relevance_relevant",
    "relevance_category",
    "relevance_score",
    "feasibility_feasible",
    "feasibility_complexity",
    "feasibility_effort",
)

_BANDS = ("act", "review", "escalate")


def _questions() -> list[dict[str, Any]]:
    """Six questions mirroring relevance.py's and feasibility.py's own prompts.

    Phrased as "relevant" (not "irrelevant") so the True/False direction
    matches the consumer-side gold-set calibration run this shadow mode is
    meant to extend.
    """
    return [
        {
            "name": "relevance_relevant",
            "type": "predicate",
            "instructions": "Is this issue relevant to the repository's scope?",
        },
        {
            "name": "relevance_category",
            "type": "choice",
            "instructions": "Which category best fits this issue?",
            "choices": list(_RELEVANCE_CATEGORIES),
        },
        {
            "name": "relevance_score",
            "type": "score",
            "instructions": (
                "On a scale of 1 (not relevant) to 10 (highly relevant), how "
                "relevant is this issue to the repository's scope?"
            ),
            "levels": [str(n) for n in range(1, 11)],
        },
        {
            "name": "feasibility_feasible",
            "type": "predicate",
            "instructions": (
                "Can the thing requested in this issue be built at all, in any software project?"
            ),
        },
        {
            "name": "feasibility_complexity",
            "type": "choice",
            "instructions": "If the issue is feasible, how complex is the implementation?",
            "choices": list(_COMPLEXITY_LEVELS),
        },
        {
            "name": "feasibility_effort",
            "type": "choice",
            "instructions": (
                "If the issue is feasible, what is the estimated implementation effort?"
            ),
            "choices": list(_EFFORT_LEVELS),
        },
    ]


def _build_state(title: str, body: str) -> str:
    """Build the `state` string decide() scores every question against.

    Reuses relevance.py's own repo-context loader (DRY) so decide() sees the
    same scope framing as the existing relevance LLM call.
    """
    context = _load_repo_context()
    return f"Repository context:\n{context}\n\nIssue title: {title}\nIssue body: {body}"


def _load_decide() -> Any:
    """Load `decide` from the pinned qte77/.github checkout via importlib."""
    path = config.settings.decide_module_path
    if not path or not Path(path).is_file():
        msg = f"decide.py not found at DECIDE_MODULE_PATH={path!r}"
        raise RuntimeError(msg)
    spec = importlib.util.spec_from_file_location("gha_issue_triage_decide_gate", path)
    if spec is None or spec.loader is None:
        msg = f"could not load decide.py spec from {path!r}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.decide


def _sanitize(name: str, answer: dict[str, Any]) -> dict[str, Any]:
    """Clamp `value` to the question's fixed list/type; round `probability`.

    A value outside the fixed list, or of the wrong type, becomes None rather
    than being echoed verbatim -- see the module docstring and `_CLOSED_SETS`.
    A "score" answer is a number: the probability-weighted, zero-based index
    into `levels`, which can land between levels (Clef's model page,
    developers.cloudflare.com/workers-ai/models/clef-flash/, read 2026-11-12;
    Clef takes Jev's wire shape). It is mapped to the nearest level label; an
    index outside the levels becomes None. A label string is still accepted.
    """
    value = answer.get("value")
    if name in _PREDICATE_NAMES:
        value = value if isinstance(value, bool) else None
    elif name in _SCORE_NAMES and isinstance(value, (int, float)) and not isinstance(value, bool):
        value = _score_level(value, _CLOSED_SETS[name])
    else:
        allowed = _CLOSED_SETS.get(name, ())
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            value = None
        else:
            value = str(value) if str(value) in allowed else None

    probability = answer.get("probability")
    if isinstance(probability, (int, float)) and not isinstance(probability, bool):
        probability = round(float(probability), 2)
    else:
        probability = None

    band = answer.get("band")
    band = band if band in _BANDS else "escalate"

    return {"value": value, "probability": probability, "band": band}


def _safe_float(value: int | float) -> float | None:
    """`float(value)`, or None if the conversion overflows.

    An absurdly large JSON integer (arbitrary-precision, unlike float) raises
    `OverflowError` from a bare `float()` call, and `math.isfinite` raises the
    same error when given such an int directly (it is not first coerced to
    float). The call sites below are reached outside `run_shadow()`'s own
    wrap-degrade `try`/`except`, so each converts through this helper instead
    of calling `float()`/`math.isfinite` on the raw value.
    """
    try:
        return float(value)
    except OverflowError:
        return None


def _score_level(index: float, levels: tuple[str, ...]) -> str | None:
    """Nearest level label for a weighted zero-based index (half rounds up), else None."""
    value = _safe_float(index)
    if value is None or not math.isfinite(value):
        return None
    nearest = math.floor(value + 0.5)
    return levels[nearest] if 0 <= nearest < len(levels) else None


def run_shadow(title: str, body: str) -> dict[str, dict[str, Any]]:
    """Ask the decision-shaped questions via decide(); never raises.

    wrap-degrade (docs/architecture.md): on any failure -- the module failing
    to load, or decide() itself raising for a malformed call -- every question
    is reported as "escalate" instead. Always returns exactly the six
    `_QUESTION_NAMES` keys, each sanitized.
    """
    try:
        decide = _load_decide()
        backend = config.settings.decide_backend
        # Reason: the LLM key/base belong to the Cloudflare endpoint. Only the
        # "clef" and "cf" backends use them; "jev" reads TYPESAFE_API_KEY from
        # the environment, so it must never receive the Cloudflare token.
        creds: dict[str, Any] = {}
        if backend in ("clef", "cf"):
            creds = {"api_key": config.settings.llm_api_key, "api_base": config.settings.api_base}
        raw = decide(
            _build_state(title, body),
            _questions(),
            backend=backend,
            model=config.settings.decide_model,
            hi=config.settings.decide_hi,
            **creds,
        )
    except Exception as exc:  # wrap-degrade boundary, see docstring above
        print(f"::warning::decide() shadow triage failed: {exc}")
        raw = {}

    for name in _SCORE_NAMES:
        _log_raw_score(name, raw.get(name, {}))
    return {name: _sanitize(name, raw.get(name, {})) for name in _QUESTION_NAMES}


def _log_raw_score(name: str, answer: dict[str, Any]) -> None:
    """Print a score answer's raw number to the job log, never to the comment.

    Lets a live run confirm the zero-based weighted index the sanitizer assumes.
    Only a float (or the value's type name) is printed, so no model-steered text
    reaches the log. Never raises: an absurdly large JSON integer overflows a
    bare `float()` call (see `_safe_float`), and this runs outside
    `run_shadow()`'s own wrap-degrade try/except.
    """
    value = answer.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        confidence = answer.get("probability")
        confidence_value = (
            _safe_float(confidence)
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
            else None
        )
        conf = f"{confidence_value:.2f}" if confidence_value is not None else "-"
        value_value = _safe_float(value)
        value_str = f"{value_value:.3f}" if value_value is not None else "overflow"
        print(f"decide-shadow raw {name}: {value_str} (confidence {conf})")
    else:
        print(f"decide-shadow raw {name}: not a number ({type(value).__name__})")


def format_comment_section(results: dict[str, dict[str, Any]]) -> str:
    """Render `run_shadow()`'s output as a fixed-format Markdown block.

    Only `value` / `probability` / `band` are shown -- never a raw backend
    error string or anything else that could carry model-steered or
    operational text into the public comment (#122 applied to this path).
    Returns "" when `results` is empty (shadow mode wasn't run).
    """
    if not results:
        return ""
    lines = [
        "#### Decision model (shadow)",
        "_Calibration only -- never sets labels or changes the analysis above._",
        "",
        "| Question | Value | Probability | Band |",
        "| --- | --- | --- | --- |",
    ]
    for name in _QUESTION_NAMES:
        answer = results.get(name, {})
        value = answer.get("value")
        probability = answer.get("probability")
        band = answer.get("band", "escalate")
        value_str = "-" if value is None else str(value)
        prob_str = "-" if probability is None else f"{probability:.2f}"
        lines.append(f"| `{name}` | {value_str} | {prob_str} | `{band}` |")
    return "\n".join(lines)
