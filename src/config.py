"""Typed, env-var-backed settings — the single source of truth for runtime config.

Field names map to env vars case-insensitively (`max_duplicates` <- `MAX_DUPLICATES`).
`action.yaml` resolves caller inputs into these env vars; tests inject config by
patching `config.settings` with an explicit `AppSettings(...)`.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime settings read once from the environment."""

    model_config = SettingsConfigDict(frozen=True)

    # LLM backend — LLM_API_KEY / API_BASE are resolved by action.yaml from the
    # api_base / llm-api-key inputs, falling back to the deprecated
    # OPENAI_API_BASE / AI_TOKEN inputs.
    llm_api_key: str = ""
    model: str = "openai/gpt-4.1"
    anthropic_api_key: str = ""
    api_base: str = ""

    # Duplicate detection
    max_duplicates: int = 10
    similarity_threshold: float = 0.6

    # GitHub Actions context
    github_event_name: str = ""
    github_event_path: str = ""
    github_repository: str = ""


settings = AppSettings()
