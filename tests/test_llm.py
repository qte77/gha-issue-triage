"""Tests for llm.py — LLM backend abstraction."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.llm import (
    _call_anthropic,
    _call_github_models,
    _call_openai_compat,
    _parse_anthropic,
    _parse_github_models,
    _request_with_retry,
    call_llm,
)


def _mock_urlopen_response(body_dict):
    """Create a mock urlopen response returning JSON."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body_dict).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_parse_github_models():
    """Extracts content from GitHub Models response."""
    # Arrange
    body = {"choices": [{"message": {"content": "hello"}}]}

    # Act
    result = _parse_github_models(body)

    # Assert
    assert result == "hello"


def test_parse_anthropic():
    """Extracts text from Anthropic response."""
    # Arrange
    body = {"content": [{"text": "world"}]}

    # Act
    result = _parse_anthropic(body)

    # Assert
    assert result == "world"


@patch("src.llm.urllib.request.urlopen")
def test_call_github_models_success(mock_urlopen):
    """GitHub Models API call returns parsed content."""
    # Arrange
    response_body = {"choices": [{"message": {"content": "test response"}}]}
    mock_urlopen.return_value = _mock_urlopen_response(response_body)

    # Act
    with patch.dict("os.environ", {"AI_TOKEN": "test-token"}, clear=False):
        result = _call_github_models("system", "user")

    # Assert
    assert result == "test response"


@patch("src.llm.urllib.request.urlopen")
def test_call_anthropic_success(mock_urlopen):
    """Anthropic API call returns parsed content."""
    # Arrange
    response_body = {"content": [{"text": "anthropic response"}]}
    mock_urlopen.return_value = _mock_urlopen_response(response_body)

    # Act
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        result = _call_anthropic("system", "user")

    # Assert
    assert result == "anthropic response"


@patch("src.llm.time.sleep")
@patch("src.llm.urllib.request.urlopen")
def test_request_with_retry_retries_on_failure(mock_urlopen, mock_sleep):
    """Retries on transient failure and succeeds on 3rd attempt."""
    # Arrange
    response_body = {"choices": [{"message": {"content": "ok"}}]}
    mock_urlopen.side_effect = [
        Exception("fail1"),
        Exception("fail2"),
        _mock_urlopen_response(response_body),
    ]

    # Act
    result = _request_with_retry("https://example.com", b"{}", {}, _parse_github_models)

    # Assert
    assert result == "ok"
    assert mock_urlopen.call_count == 3
    assert mock_sleep.call_count == 2


@patch("src.llm.time.sleep")
@patch("src.llm.urllib.request.urlopen", side_effect=Exception("permanent"))
def test_request_with_retry_raises_after_max(mock_urlopen, mock_sleep):
    """Raises RuntimeError after all retries exhausted."""
    # Arrange / Act / Assert
    with pytest.raises(RuntimeError, match="failed after"):
        _request_with_retry("https://example.com", b"{}", {}, _parse_github_models)


@patch("src.llm.OPENAI_API_BASE", "")
@patch("src.llm.ANTHROPIC_API_KEY", "")
@patch("src.llm._call_github_models", return_value="github response")
def test_call_llm_uses_github_models_by_default(mock_gh):
    """call_llm dispatches to GitHub Models when no Anthropic key or OpenAI base."""
    # Act
    result = call_llm("sys", "usr")

    # Assert
    assert result == "github response"
    mock_gh.assert_called_once_with("sys", "usr")


@patch("src.llm.OPENAI_API_BASE", "")
@patch("src.llm.ANTHROPIC_API_KEY", "sk-test")
@patch("src.llm._call_anthropic", return_value="anthropic response")
def test_call_llm_uses_anthropic_when_key_set(mock_ant):
    """call_llm dispatches to Anthropic when key is set."""
    # Act
    result = call_llm("sys", "usr")

    # Assert
    assert result == "anthropic response"
    mock_ant.assert_called_once_with("sys", "usr")


@patch("src.llm.OPENAI_API_BASE", "https://api.mistral.ai/v1")
@patch("src.llm.ANTHROPIC_API_KEY", "sk-test")
@patch("src.llm._call_openai_compat", return_value="openai-compat response")
def test_call_llm_prefers_openai_compat_when_base_set(mock_oc):
    """OPENAI_API_BASE takes precedence over ANTHROPIC_API_KEY."""
    # Act
    result = call_llm("sys", "usr")

    # Assert
    assert result == "openai-compat response"
    mock_oc.assert_called_once_with("sys", "usr")


@patch("src.llm.urllib.request.urlopen")
@patch("src.llm.OPENAI_API_BASE", "https://api.mistral.ai/v1")
def test_call_openai_compat_https_success(mock_urlopen):
    """OpenAI-compatible cloud endpoint returns parsed content."""
    # Arrange
    response_body = {"choices": [{"message": {"content": "mistral response"}}]}
    mock_urlopen.return_value = _mock_urlopen_response(response_body)

    # Act
    with patch.dict("os.environ", {"AI_TOKEN": "mistral-key"}, clear=False):
        result = _call_openai_compat("system", "user")

    # Assert
    assert result == "mistral response"
    # URL is built from base + /chat/completions
    called_url = mock_urlopen.call_args[0][0].full_url
    assert called_url == "https://api.mistral.ai/v1/chat/completions"


@patch("src.llm.urllib.request.urlopen")
@patch("src.llm.OPENAI_API_BASE", "http://localhost:11434/v1/")  # trailing slash, http
def test_call_openai_compat_local_http_allowed(mock_urlopen):
    """Localhost http is permitted for self-hosted backends (Ollama)."""
    # Arrange
    response_body = {"choices": [{"message": {"content": "ollama"}}]}
    mock_urlopen.return_value = _mock_urlopen_response(response_body)

    # Act
    result = _call_openai_compat("system", "user")

    # Assert
    assert result == "ollama"
    called_url = mock_urlopen.call_args[0][0].full_url
    assert called_url == "http://localhost:11434/v1/chat/completions"


def test_request_with_retry_rejects_non_local_http():
    """Plain http to a non-local host is refused."""
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="non-https"):
        _request_with_retry("http://evil.example.com/v1", b"{}", {}, _parse_github_models)
