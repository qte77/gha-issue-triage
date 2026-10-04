"""Configurable LLM backend: OpenAI-compatible, Anthropic, or GitHub Models (default)."""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from os import getenv
from urllib.parse import urlparse

from errors import TriageFailure, TriageFailureError

# LLM_API_KEY / API_BASE are resolved by action.yaml from the api_base /
# llm-api-key inputs, falling back to the deprecated OPENAI_API_BASE /
# AI_TOKEN inputs — this module only ever sees the resolved names.
LLM_API_KEY = getenv("LLM_API_KEY", "")
MODEL = getenv("MODEL", "openai/gpt-4.1")
ANTHROPIC_API_KEY = getenv("ANTHROPIC_API_KEY", "")
API_BASE = getenv("API_BASE", "")

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2

_GITHUB_MODELS_HOST = "models.github.ai"
_ANTHROPIC_HOST = "api.anthropic.com"


def _gone_failure(backend: str, host: str) -> TriageFailure:
    """Map an HTTP 410 Gone response to a TriageFailure (not retried)."""
    if backend == "github":
        return TriageFailure(
            class_name="github-models-retired",
            status=410,
            summary="GitHub Models inference API has been retired (HTTP 410 Gone).",
            fix_markdown=(
                "GitHub Models was retired 2026-07-30. Switch to an OpenAI-compatible "
                "backend via `api_base` + `llm-api-key` (see "
                "`docs/integrations.md#path-b--openai-compatible-backend`), "
                "or to Anthropic via `ANTHROPIC_API_KEY`."
            ),
        )
    return TriageFailure(
        class_name="provider-endpoint-gone",
        status=410,
        summary=f"{host} returned HTTP 410 Gone — the endpoint may have moved or been retired.",
        fix_markdown=f"Check `{host}`'s current API docs for the correct `api_base` path.",
    )


def _http_error_to_failure(exc: urllib.error.HTTPError, backend: str, host: str) -> TriageFailure:
    """Map an HTTPError from a known backend to a TriageFailure."""
    code = exc.code
    if code == 410:
        return _gone_failure(backend, host)
    if code == 429:
        return TriageFailure(
            class_name="llm-rate-limit",
            status=429,
            summary="LLM backend rate-limit hit (HTTP 429).",
            fix_markdown=(
                "Re-run the workflow after `Retry-After` elapses. For sustained traffic, "
                "supply a PAT via `llm-api-key` (higher per-user quota) or switch to Path B "
                "per `docs/integrations.md`."
            ),
        )
    if 500 <= code <= 599:
        return TriageFailure(
            class_name="llm-upstream",
            status=code,
            summary=f"LLM backend returned {code} (transient upstream error).",
            fix_markdown="Re-run the workflow. No caller change needed.",
        )
    if code in (401, 403):
        if backend == "github":
            return TriageFailure(
                class_name="missing-models-perm",
                status=code,
                summary="GitHub Models inference call returned 401/403.",
                fix_markdown=(
                    "Add `permissions: models: read` to the caller workflow, or supply a PAT "
                    "via `llm-api-key`. See `docs/integrations.md#auth-for-llm-api-key`."
                ),
            )
        if backend == "anthropic":
            return TriageFailure(
                class_name="invalid-anthropic-key",
                status=401,
                summary="Anthropic API rejected the key.",
                fix_markdown=(
                    "`ANTHROPIC_API_KEY` is invalid or expired. Rotate or unset to fall back "
                    "to GitHub Models."
                ),
            )
        # openai-compat
        return TriageFailure(
            class_name="invalid-ai-token",
            status=401,
            summary="OpenAI-compatible endpoint rejected the bearer token.",
            fix_markdown=(
                f"`llm-api-key` is invalid for `{host}`. Check the provider's key + endpoint URL."
            ),
        )
    # Unhandled HTTP error — re-raise as-is so existing RuntimeError path handles it
    raise exc


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call LLM with retry and backoff.

    Dispatch order: OpenAI-compatible (if API_BASE set) → Anthropic
    (if ANTHROPIC_API_KEY set) → GitHub Models (default, retired — see
    `docs/integrations.md#path-b--openai-compatible-backend`).
    """
    if API_BASE:
        return _call_openai_compat(system_prompt, user_prompt)
    if ANTHROPIC_API_KEY:
        return _call_anthropic(system_prompt, user_prompt)
    return _call_github_models(system_prompt, user_prompt)


def _call_github_models(system_prompt: str, user_prompt: str) -> str:
    """Call GitHub Models API via urllib."""
    url = "https://models.github.ai/inference/chat/completions"
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 1000,
            "temperature": 0.3,
        }
    ).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    try:
        return _request_with_retry(url, payload, headers, _parse_github_models)
    except urllib.error.HTTPError as exc:
        failure = _http_error_to_failure(exc, "github", _GITHUB_MODELS_HOST)
        raise TriageFailureError(failure) from exc
    except urllib.error.URLError as exc:
        raise TriageFailureError(
            TriageFailure(
                class_name="llm-network",
                status=None,
                summary=f"Could not reach {_GITHUB_MODELS_HOST} from the runner.",
                fix_markdown="Likely transient runner-side; re-run the workflow.",
            )
        ) from exc


def _call_openai_compat(system_prompt: str, user_prompt: str) -> str:
    """Call an OpenAI-compatible Chat Completions endpoint (Cloudflare Workers AI, Mistral, ...)."""
    url = f"{API_BASE.rstrip('/')}/chat/completions"
    host = urlparse(API_BASE).hostname or API_BASE
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 1000,
            "temperature": 0.3,
        }
    ).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    try:
        return _request_with_retry(url, payload, headers, _parse_github_models)
    except urllib.error.HTTPError as exc:
        raise TriageFailureError(_http_error_to_failure(exc, "openai-compat", host)) from exc
    except urllib.error.URLError as exc:
        raise TriageFailureError(
            TriageFailure(
                class_name="llm-network",
                status=None,
                summary=f"Could not reach {host} from the runner.",
                fix_markdown="Likely transient runner-side; re-run the workflow.",
            )
        ) from exc


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    """Call Anthropic Messages API via urllib."""
    url = "https://api.anthropic.com/v1/messages"
    payload = json.dumps(
        {
            "model": "claude-sonnet-4-6",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
    ).encode()

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    try:
        return _request_with_retry(url, payload, headers, _parse_anthropic)
    except urllib.error.HTTPError as exc:
        raise TriageFailureError(_http_error_to_failure(exc, "anthropic", _ANTHROPIC_HOST)) from exc
    except urllib.error.URLError as exc:
        raise TriageFailureError(
            TriageFailure(
                class_name="llm-network",
                status=None,
                summary=f"Could not reach {_ANTHROPIC_HOST} from the runner.",
                fix_markdown="Likely transient runner-side; re-run the workflow.",
            )
        ) from exc


def _decode_response(resp, host: str, status: int | None) -> str:
    """Parse a response body as JSON, raising a clear, non-retried failure on malformed input.

    Never includes the bearer token — only the host and HTTP status, which are
    safe to surface in a public issue comment.
    """
    raw = resp.read()
    try:
        return json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TriageFailureError(
            TriageFailure(
                class_name="llm-bad-response",
                status=status,
                summary=f"{host} returned an empty or non-JSON response body (HTTP {status}).",
                fix_markdown=(
                    "Verify `api_base` points at an OpenAI-compatible Chat Completions "
                    "endpoint and that `MODEL` is a valid model ID for that provider."
                ),
            )
        ) from exc


def _request_with_retry(
    url: str,
    payload: bytes,
    headers: dict[str, str],
    parser: Callable[[dict], str],
) -> str:
    """Send HTTP request with exponential backoff retry."""
    if not (url.startswith("https://") or _is_local_http(url)):
        msg = f"Refusing to open non-https URL: {url}"
        raise ValueError(msg)
    host = urlparse(url).hostname or url
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")  # noqa: S310  # URL scheme validated at line 105
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310  # nosec B310
                status = getattr(resp, "status", None)
                body = _decode_response(resp, host, status)
                return _extract_content(body, parser, host, status)
        except Exception as exc:
            if isinstance(exc, (urllib.error.HTTPError, urllib.error.URLError, TriageFailureError)):
                raise
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                print(f"LLM request failed (attempt {attempt + 1}): {exc}. Retrying in {delay}s")
                time.sleep(delay)

    msg = f"LLM request failed after {MAX_RETRIES} attempts: {last_error}"
    raise RuntimeError(msg)


def _extract_content(
    body: dict, parser: Callable[[dict], str], host: str, status: int | None
) -> str:
    """Run a backend-specific parser, raising a clear failure when the shape is unexpected."""
    try:
        return parser(body)
    except (KeyError, IndexError, TypeError) as exc:
        raise TriageFailureError(
            TriageFailure(
                class_name="llm-bad-response",
                status=status,
                summary=f"{host} returned a response body missing the expected fields.",
                fix_markdown=(
                    "Verify `api_base` points at an OpenAI-compatible Chat Completions "
                    "endpoint and that `MODEL` is a valid model ID for that provider."
                ),
            )
        ) from exc


def _is_local_http(url: str) -> bool:
    """Allow plain http only for localhost (self-hosted backends like Ollama)."""
    return url.startswith(("http://localhost", "http://127.0.0.1"))


def _parse_github_models(body: dict) -> str:
    """Extract content from GitHub Models API response."""
    return body["choices"][0]["message"]["content"]


def _parse_anthropic(body: dict) -> str:
    """Extract content from Anthropic Messages API response."""
    return body["content"][0]["text"]
