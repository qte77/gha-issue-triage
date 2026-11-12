"""Tests for decide_shadow.py — decide() gate shadow-mode calibration.

Shadow mode never sets labels and never changes the existing triage output;
these tests mock `decide()` itself (never call the network) and assert the
wrap-degrade contract: any failure (loader, malformed call, backend/network)
degrades to an all-"escalate" result rather than raising or going silent.
"""

import pytest

from src.decide_shadow import (
    _QUESTION_NAMES,
    _log_raw_score,
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


@pytest.mark.parametrize(
    ("score", "level"),
    [(0.0, "1"), (6.4, "7"), (6.5, "8"), (9.0, "10"), (3, "4")],
)
def test_sanitize_score_maps_zero_based_weighted_index_to_level(score, level):
    """Clef/Jev answer a score question with a number: the probability-weighted,
    zero-based level index, which can land between levels (Clef output schema:
    "Probability-weighted level; can land between levels"; "0 = lowest level").
    The shadow shows the nearest level label."""
    result = _sanitize("relevance_score", _answer(value=score, probability=0.4, band="review"))
    assert result["value"] == level


@pytest.mark.parametrize("score", [-0.6, 9.6, float("nan"), float("inf")])
def test_sanitize_score_index_outside_levels_becomes_none(score):
    result = _sanitize("relevance_score", _answer(value=score, probability=0.4))
    assert result["value"] is None


def test_sanitize_score_level_label_passes_through():
    result = _sanitize("relevance_score", _answer(value="7", probability=0.4))
    assert result["value"] == "7"


@pytest.mark.parametrize(
    ("score", "level"),
    [(1, "1"), (7, "7"), (10, "10"), (6.6, "7")],
)
def test_sanitize_score_cf_backend_maps_literal_value_not_zero_based_index(score, level):
    """The "cf" backend is an uncalibrated chat model answering this question's
    own "scale of 1 to 10" instructions text literally, not decide.py's generic
    zero-based-index hint meant for Clef/Jev's calibrated score head (#133's
    mapping only matches that wire shape). Reading a cf answer as zero-based
    is off by one: literal "7" would render "8", and literal "10" would
    render "-" (index 10 is out of range for a 10-level list)."""
    result = _sanitize(
        "relevance_score",
        {"value": score, "probability": None, "band": "escalate", "source": "cf"},
    )
    assert result["value"] == level


def test_sanitize_score_non_cf_source_still_uses_zero_based_index():
    """Regression pin: a Clef-sourced (or unlabeled) answer keeps #133's
    existing zero-based-weighted-index mapping -- this fix must not change it."""
    result = _sanitize(
        "relevance_score",
        {"value": 6.5, "probability": 0.4, "band": "review", "source": "clef"},
    )
    assert result["value"] == "8"


def test_sanitize_rounds_probability_to_two_decimals():
    result = _sanitize("relevance_category", _answer(value="bug", probability=0.123456))
    assert result["probability"] == 0.12


def test_sanitize_non_numeric_probability_becomes_none():
    result = _sanitize("relevance_category", _answer(value="bug", probability="high"))
    assert result["probability"] is None


def test_sanitize_overflow_probability_becomes_none_without_raising():
    """Same OverflowError boundary as the raw-score log, reached through
    _sanitize()'s own probability rounding (also outside run_shadow()'s
    wrap-degrade try/except)."""
    result = _sanitize("relevance_category", _answer(value="bug", probability=10**400))
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


def test_run_shadow_jev_backend_does_not_get_the_cloudflare_credentials(monkeypatch, settings):
    """backend "jev": the Cloudflare key/base must not be sent; decide() reads TYPESAFE_* itself."""
    calls = {}

    def fake_decide(state, questions, **kwargs):
        calls["kwargs"] = kwargs
        return {}

    jev = settings.model_copy(update={"decide_backend": "jev", "decide_model": "jev-1.13.0"})
    monkeypatch.setattr("src.decide_shadow.config.settings", jev)
    monkeypatch.setattr("src.decide_shadow._load_decide", lambda: fake_decide)

    run_shadow("Some title", "Some body")

    assert calls["kwargs"]["backend"] == "jev"
    assert "api_key" not in calls["kwargs"]
    assert "api_base" not in calls["kwargs"]


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


# ---------------------------------------------------------------------------
# raw score logging — lets a live run confirm the score's indexing (plan 0013 A6)
# ---------------------------------------------------------------------------


def test_run_shadow_logs_raw_numeric_score(monkeypatch, settings, capsys):
    """The raw score number goes to the job log (not the comment), so a live run
    shows whether it is a zero-based weighted index."""

    def fake_decide(*a, **kw):
        return {"relevance_score": {"value": 6.4321, "probability": 0.04, "band": "escalate"}}

    monkeypatch.setattr("src.decide_shadow._load_decide", lambda: fake_decide)

    run_shadow("Title", "Body")

    assert "decide-shadow raw relevance_score: 6.432 (confidence 0.04)" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["## PROBE @someone", None, True])
def test_run_shadow_never_logs_non_numeric_score_text(monkeypatch, settings, capsys, value):
    """A non-numeric value is logged by type name only -- never echoed."""

    def fake_decide(*a, **kw):
        return {"relevance_score": {"value": value, "probability": None, "band": "escalate"}}

    monkeypatch.setattr("src.decide_shadow._load_decide", lambda: fake_decide)

    run_shadow("Title", "Body")

    out = capsys.readouterr().out
    assert f"decide-shadow raw relevance_score: not a number ({type(value).__name__})" in out
    assert "PROBE" not in out


def test_log_raw_score_overflow_value_does_not_raise(capsys):
    """An absurdly large JSON integer (outside float range) must degrade, not
    raise OverflowError -- a bare `float(value)` call (and `math.isfinite` on
    a raw int) raises for such a value, and this runs outside run_shadow()'s
    own wrap-degrade try/except."""
    _log_raw_score("relevance_score", {"value": 10**400, "probability": 0.5})
    assert "overflow" in capsys.readouterr().out.lower()


def test_run_shadow_overflow_score_degrades_instead_of_raising(monkeypatch, settings, capsys):
    """Same boundary as above, exercised through run_shadow()'s full path:
    the raw-score job-log line and _sanitize's index mapping both execute
    after run_shadow()'s own try/except, so neither may raise."""

    def fake_decide(*a, **kw):
        return {"relevance_score": {"value": 10**400, "probability": 0.5, "band": "review"}}

    monkeypatch.setattr("src.decide_shadow._load_decide", lambda: fake_decide)

    result = run_shadow("Title", "Body")  # must not raise

    assert result["relevance_score"]["value"] is None
    assert "overflow" in capsys.readouterr().out.lower()
