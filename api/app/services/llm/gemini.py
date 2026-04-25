"""Gemini provider — uses Google's OpenAI-compatible endpoint so the swap from
Z.AI is just a base_url + model change.

Endpoint: https://generativelanguage.googleapis.com/v1beta/openai/
Free-tier models: gemini-2.5-flash, gemini-2.5-flash-lite
"""

from __future__ import annotations

from app.config import Settings
from app.services.llm.openai_compatible import OpenAICompatibleProvider


class GeminiProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
            name=f"gemini:{settings.gemini_model}",
        )
