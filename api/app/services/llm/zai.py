"""Z.AI provider — OpenAI-compatible at https://api.z.ai/api/paas/v4/."""

from __future__ import annotations

from app.config import Settings
from app.services.llm.openai_compatible import OpenAICompatibleProvider


class ZaiProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            api_key=settings.zai_api_key,
            base_url=settings.zai_base_url,
            model=settings.zai_model,
            name=f"zai:{settings.zai_model}",
        )
