"""Gemini provider — uses Google's OpenAI-compatible endpoint so the swap from
Z.AI is just a base_url + model change.

Endpoint: https://generativelanguage.googleapis.com/v1beta/openai/
Default model: gemini-3-flash-preview. Gemma models (when configured) emit
<thought> reasoning blocks and do not support response_format=json_object —
the provider auto-disables JSON mode for any ``gemma*`` model name and parsers
downstream strip the reasoning tags.
"""

from __future__ import annotations

from app.config import Settings
from app.services.llm.openai_compatible import OpenAICompatibleProvider


class GeminiProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        # Gemma models served via the AI Studio OpenAI-compat endpoint do not
        # support response_format=json_object — rely on prompting instead.
        is_gemma = settings.gemini_model.lower().startswith("gemma")
        super().__init__(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
            name=f"gemini:{settings.gemini_model}",
            json_mode=not is_gemma,
        )
