"""Tests for config.py — typed env-var settings."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config import AppSettings


def test_settings_read_and_coerce_env_vars():
    """Env vars are read case-insensitively and coerced to the field types."""
    # Arrange
    env = {
        "MAX_DUPLICATES": "3",
        "SIMILARITY_THRESHOLD": "0.75",
        "API_BASE": "https://api.example.com/v1",
        "GITHUB_REPOSITORY": "qte77/gha-issue-triage",
    }

    # Act
    with patch.dict("os.environ", env, clear=True):
        settings = AppSettings()

    # Assert
    assert settings.max_duplicates == 3
    assert settings.similarity_threshold == 0.75
    assert settings.api_base == "https://api.example.com/v1"
    assert settings.github_repository == "qte77/gha-issue-triage"


def test_settings_defaults_when_env_empty():
    """Unset env vars fall back to the documented defaults."""
    # Act
    with patch.dict("os.environ", {}, clear=True):
        settings = AppSettings()

    # Assert
    assert settings.max_duplicates == 10
    assert settings.similarity_threshold == 0.6
    assert settings.model == "openai/gpt-4.1"
    assert settings.llm_api_key == ""
    assert settings.github_event_path == ""
    # decide() shadow mode: off by default, never silently enabled.
    assert settings.decide_shadow is False
    assert settings.decide_backend == "clef"
    assert settings.decide_model == "clef"
    assert settings.decide_hi == 0.75
    assert settings.decide_module_path == ""


def test_settings_decide_shadow_env_vars():
    """decide() shadow inputs are read and coerced like any other setting."""
    # Arrange
    env = {
        "DECIDE_SHADOW": "true",
        "DECIDE_BACKEND": "jev",
        "DECIDE_MODEL": "jev-1.13.0",
        "DECIDE_HI": "0.85",
        "DECIDE_MODULE_PATH": "decide-gate/decide.py",
    }

    # Act
    with patch.dict("os.environ", env, clear=True):
        settings = AppSettings()

    # Assert
    assert settings.decide_shadow is True
    assert settings.decide_backend == "jev"
    assert settings.decide_model == "jev-1.13.0"
    assert settings.decide_hi == 0.85
    assert settings.decide_module_path == "decide-gate/decide.py"


def test_settings_invalid_number_fails_loud():
    """A non-numeric MAX_DUPLICATES raises instead of silently degrading."""
    # Act / Assert
    with (
        patch.dict("os.environ", {"MAX_DUPLICATES": "ten"}, clear=True),
        pytest.raises(ValidationError),
    ):
        AppSettings()


def test_settings_are_frozen():
    """Settings can't be mutated mid-run."""
    # Arrange
    settings = AppSettings(max_duplicates=5)

    # Act / Assert
    with pytest.raises(ValidationError):
        settings.max_duplicates = 6
