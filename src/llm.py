"""Configurable LLM backend: GitHub Models API (default) or Anthropic API."""

import json
import time
import urllib.request
from collections.abc import Callable
from os import getenv

AI_TOKEN = getenv("AI_TOKEN", "")
MODEL = getenv("MODEL", "openai/gpt-4.1")
ANTHROPIC_API_KEY = getenv("ANTHROPIC_API_KEY", "")

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call LLM with retry and backoff. Uses Anthropic if key is set, else GitHub Models."""
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
        "Authorization": f"Bearer {AI_TOKEN}",
    }

    return _request_with_retry(url, payload, headers, _parse_github_models)


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

    return _request_with_retry(url, payload, headers, _parse_anthropic)


def _request_with_retry(
    url: str,
    payload: bytes,
    headers: dict[str, str],
    parser: Callable[[dict], str],
) -> str:
    """Send HTTP request with exponential backoff retry."""
    if not url.startswith("https://"):
        msg = f"Refusing to open non-https URL: {url}"
        raise ValueError(msg)
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310  # nosec B310
                body = json.loads(resp.read().decode())
                return parser(body)
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2**attempt)
                print(f"LLM request failed (attempt {attempt + 1}): {exc}. Retrying in {delay}s")
                time.sleep(delay)

    msg = f"LLM request failed after {MAX_RETRIES} attempts: {last_error}"
    raise RuntimeError(msg)


def _parse_github_models(body: dict) -> str:
    """Extract content from GitHub Models API response."""
    return body["choices"][0]["message"]["content"]


def _parse_anthropic(body: dict) -> str:
    """Extract content from Anthropic Messages API response."""
    return body["content"][0]["text"]
