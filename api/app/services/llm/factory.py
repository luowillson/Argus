"""Resolve which LLM provider to use based on settings."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.services.llm.gemini import GeminiProvider
from app.services.llm.provider import LLMProvider
from app.services.llm.zai import ZaiProvider


def make_llm_provider(settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    name = s.llm_provider.lower()
    if name == "zai":
        return ZaiProvider(s)
    if name == "gemini":
        return GeminiProvider(s)
    raise ValueError(
        f"unknown LLM_PROVIDER {s.llm_provider!r}; expected 'zai' or 'gemini'"
    )
