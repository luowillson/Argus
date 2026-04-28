"""Resolve which LLM provider to use based on settings.

Single source of truth for "which model is active right now":
``effective_llm_model_name()`` reads from settings and is used everywhere so
that changing one variable in `.env` (and restarting) flips the entire app.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.services.llm.gemini import GeminiProvider
from app.services.llm.provider import LLMProvider


def make_llm_provider(settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    name = s.llm_provider.lower()
    if name == "gemini":
        return GeminiProvider(s)
    raise ValueError(
        f"unknown LLM_PROVIDER {s.llm_provider!r}; expected 'gemini'"
    )


def effective_llm_model_name(settings: Settings | None = None) -> str:
    """Return the provider:model identifier the system would use right now.

    This must match the ``name`` attribute that the corresponding provider
    sets, so callers can compare it against ``ai_insights.model`` in the
    database to detect stale cache entries.
    """
    s = settings or get_settings()
    name = s.llm_provider.lower()
    if name == "gemini":
        return f"gemini:{s.gemini_model}"
    raise ValueError(
        f"unknown LLM_PROVIDER {s.llm_provider!r}; expected 'gemini'"
    )
