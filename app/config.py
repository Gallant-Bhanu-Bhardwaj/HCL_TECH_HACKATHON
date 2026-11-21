"""Environment-backed settings loader.

SHARED-FROZEN (docs/architecture.md §8) — the env var names here are the
contract; add new ones only via an acknowledged PR.

Env vars (docs/api-contracts.md §13):
    MOCK_LLM, DB_PATH, OLLAMA_URL, LLM_MODEL, EMBED_MODEL, TZ_NAME,
    TRACE_STORE_PROMPTS, DEFAULT_AS_OF (optional)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mock_llm: bool
    db_path: str
    ollama_url: str
    llm_model: str
    embed_model: str
    tz_name: str
    trace_store_prompts: bool
    default_as_of: str | None


def load_settings() -> Settings:
    """Read configuration from the environment. Call once at app startup."""
    return Settings(
        mock_llm=_bool("MOCK_LLM", True),
        db_path=os.environ.get("DB_PATH", "ujjwal_rail.db"),
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        llm_model=os.environ.get("LLM_MODEL", "llama3.2"),
        embed_model=os.environ.get("EMBED_MODEL", "nomic-embed-text"),
        tz_name=os.environ.get("TZ_NAME", "Asia/Kolkata"),
        trace_store_prompts=_bool("TRACE_STORE_PROMPTS", False),
        default_as_of=os.environ.get("DEFAULT_AS_OF"),
    )


settings = load_settings()
