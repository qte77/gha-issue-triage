"""Tests for decide_shadow.py — decide() gate shadow-mode calibration.

Shadow mode never sets labels and never changes the existing triage output;
these tests mock `decide()` itself (never call the network) and assert the
wrap-degrade contract: any failure (loader, malformed call, backend/network)
degrades to an all-"escalate" result rather than raising or going silent.
"""

import pytest

from src.decide_shadow import (
    _QUESTION_NAMES,
    _questions,
    _sanitize,
    format_comment_section,
    run_shadow,
)


def _answer(value=None, probability=None, band="escalate"):
    return {"value": value, "probability": probability, "band": band}


# ---------------------------------------------------------------------------
# _questions() — shape sent to decide()
# ---------------------------------------------------------------------------


def test_questions_cover_all_six_fields():
    """One question per decision-shaped field, matching _QUESTION_NAMES."""
    names = {q["name"] for q in _questions()}
    assert names == set(_QUESTION_NAMES)


def test_questions_have_required_shape_per_type():
    """predicate needs only instructions; choice/score need their criteria list."""
    by_name = {q["name"]: q for q in _questions()}
    assert by_name["relevance_relevant"]["type"] == "predicate"
    assert by_name["feasibility_feasible"]["type"] == "predicate"
    assert by_name["relevance_category"]["type"] == "choice"
    assert "invalid" in by_name["relevance_category"]["choices"]
    assert by_name["feasibility_complexity"]["choices"] == ["low", "medium", "high"]
    assert by_name["feasibility_effort"]["choices"] == ["hours", "days", "weeks"]
    assert by_name["relevance_score"]["type"] == "score"
    assert by_name["relevance_score"]["levels"] == [str(n) for n in range(1, 11)]
    for q in _questions():
        assert q["instructions"]


# ---------------------------------------------------------------------------
# _sanitize() — never model text (#122 discipline applied to the new path)
# ---------------------------------------------------------------------------


def test_sanitize_predicate_keeps_bool():
    result = _sanitize("relevance_relevant", _answer(value=True, probability=0.9123, band="act"))
    assert result == {"value": True, "probability": 0.91, "band": "act"}


def test_sanitize_predicate_rejects_non_bool():
    """A predicate answer that isn't a bool (malformed backend reply) becomes None."""
    result = _sanitize("feasibility_feasible", _answer(value="yes", probability=0.8, band="act"))
    assert result["value"] is None


def test_sanitize_choice_in_fixed_list_passes_through():
    result = _sanitize(
        "feasibility_complexity", _answer(value="medium", probability=0.7, band="review")
    )
    assert result == {"value": "medium", "probability": 0.7, "band": "review"}


def test_sanitize_choice_outside_fixed_list_becomes_none():
    """Free text outside the requested choices never reaches the rendered output."""
    probe = "## PROBE **x** @someone"
    result = _sanitize("feasibility_complexity", _answer(value=probe, probability=0.6, band="act"))
    assert result["value"] is None


def test_sanitize_score_outside_levels_becomes_none():
    result = _sanitize("relevance_score", _answer(value="not-a-level", probability=0.5))
    assert result["value"] is None


def test_sanitize_score_in_levels_normalizes_to_str():
    result = _sanitize("relevance_score", _answer(value=7, probability=0.4, band="review"))
    assert result["value"] == "7"


def test_sanitize_rounds_probability_to_two_decimals():
    result = _sanitize("relevance_category", _answer(value="bug", probability=0.123456))
    assert result["probability"] == 0.12


def test_sanitize_non_numeric_probability_becomes_none():
    result = _sanitize("relevance_category", _answer(value="bug", probability="high"))
    assert result["probability"] is None


def test_sanitize_unknown_band_falls_back_to_escalate():
    result = _sanitize("relevance_category", _answer(value="bug", probability=0.9, band="???"))
    assert result["band"] == "escalate"


# ---------------------------------------------------------------------------
# run_shadow() — wrap-degrade boundary
# ---------------------------------------------------------------------------


@pytest.fixture
def settings(monkeypatch):
    """Point config.settings at a usable decide_module_path and backend config."""
    import config

    s = config.AppSettings(
        decide_shadow=True,
        decide_backend="clef",
        decide_model="clef",
        decide_hi=0.75,
        decide_module_path="/fake/decide.py",
        llm_api_key="cf-token",
        api_base="https://api.cloudflare.com/client/v4/accounts/x/ai/v1",
    )
    monkeypatch.setattr("src.decide_shadow.config.settings", s)
    return s


def test_run_shadow_success_sanitizes_every_question(monkeypatch, settings):
    """A successful decide() call is sanitized and keyed by all six question names."""
    raw = {
        "relevance_relevant": _answer(True, 0.9, "act"),
        "relevance_category": _answer("bug", 0.8, "review"),
        "relevance_score": _answer("7", 0.6, "review"),
        "feasibility_feasible": _answer(True, 0.95, "act"),
        "feasibility_complexity": _answer("low", 0.7, "review"),
        "feasibility_effort": _answer("days", 0.7, "review"),
    }
    mock_decide = lambda *a, **kw: raw  # noqa: E731
    monkeypatch.setattr("src.decide_shadow._load_decide", lambda: mock_decide)

    result = run_shadow("Title", "Body")

    assert set(result) == set(_QUESTION_NAMES)
    assert result["relevance_relevant"]["value"] is True
    assert result["feasibility_complexity"]["value"] == "low"


def test_run_shadow_passes_backend_config_to_decide(monkeypatch, settings):
    """decide() is called with the configured backend/model/hi and shared creds."""
    calls = {}

    def fake_decide(state, questions, **kwargs):
        calls["state"] = state
        calls["questions"] = questions
        calls["kwargs"] = kwargs
        return {}

    monkeypatch.setattr("src.decide_shadow._load_decide", lambda: fake_decide)

    run_shadow("Some title", "Some body")

    assert calls["kwargs"]["backend"] == "clef"
    assert calls["kwargs"]["model"] == "clef"
    assert calls["kwargs"]["hi"] == 0.75
    assert calls["kwargs"]["api_key"] == "cf-token"
    assert calls["kwargs"]["api_base"] == "https://api.cloudflare.com/client/v4/accounts/x/ai/v1"
    assert "Some title" in calls["state"]
    assert "Some body" in calls["state"]


def test_run_shadow_loader_failure_degrades_to_all_escalate(monkeypatch, settings, capsys):
    """decide.py missing/unloadable -> every question escalates, never raises."""

    def boom():
        raise RuntimeError("decide.py not found at DECIDE_MODULE_PATH='/fake/decide.py'")

    monkeypatch.setattr("src.decide_shadow._load_decide", boom)

    result = run_shadow("Title", "Body")

    assert set(result) == set(_QUESTION_NAMES)
    escalate = {"value": None, "probability": None, "band": "escalate"}
    assert all(r == escalate for r in result.values())
    assert "::warning::decide() shadow triage failed" in capsys.readouterr().out


def test_run_shadow_decide_call_failure_degrades_to_all_escalate(monkeypatch, settings, capsys):
    """decide() itself raising (e.g. DecideError on a malformed call) never propagates."""

    def fake_decide(*a, **kw):
        raise ValueError("unknown backend: 'bogus'")

    monkeypatch.setattr("src.decide_shadow._load_decide", lambda: fake_decide)

    result = run_shadow("Title", "Body")

    assert all(r["band"] == "escalate" for r in result.values())
    assert "::warning::" in capsys.readouterr().out


def test_run_shadow_missing_question_in_response_escalates_that_field(monkeypatch, settings):
    """decide() returning a partial dict still yields a full 6-key result."""
    monkeypatch.setattr(
        "src.decide_shadow._load_decide",
        lambda: lambda *a, **kw: {"relevance_relevant": _answer(True, 0.9, "act")},
    )

    result = run_shadow("Title", "Body")

    assert set(result) == set(_QUESTION_NAMES)
    assert result["relevance_relevant"]["value"] is True
    assert result["relevance_category"] == {"value": None, "probability": None, "band": "escalate"}


# ---------------------------------------------------------------------------
# format_comment_section() — fixed-format markdown, no free text
# ---------------------------------------------------------------------------


def test_format_comment_section_empty_results_is_empty_string():
    assert format_comment_section({}) == ""


def test_format_comment_section_renders_all_questions_in_order():
    results = {
        name: _sanitize(name, _answer(value=None, probability=None, band="escalate"))
        for name in _QUESTION_NAMES
    }
    results["relevance_relevant"] = _sanitize("relevance_relevant", _answer(True, 0.9123, "act"))

    section = format_comment_section(results)

    assert "decision model" in section.lower()
    assert "`relevance_relevant`" in section
    assert "0.91" in section
    assert "`act`" in section
    # Deterministic row order
    rel_idx = section.index("relevance_relevant")
    cat_idx = section.index("relevance_category")
    assert rel_idx < cat_idx


def test_format_comment_section_never_contains_raw_error_text():
    """Only value/probability/band are rendered -- no raw backend/network strings."""
    results = {name: _sanitize(name, _answer()) for name in _QUESTION_NAMES}
    section = format_comment_section(results)
    assert "Traceback" not in section
    assert "HTTP" not in section
