"""Generic OpenAI-compatible LLM provider.

Z.AI, Gemini (via /v1beta/openai/), OpenRouter, Groq, and OpenAI itself all
accept the same Chat Completions request shape. Subclass by passing a
`base_url` + `api_key` + default `model`.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from app.services.llm.provider import JSONResponse, LLMProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        name: str,
        json_mode: bool = True,
        timeout: float = 90.0,
    ) -> None:
        if not api_key:
            raise ValueError(f"{name}: api_key is required")
        # Without a timeout the SDK will wait forever; Gemma's reasoning passes
        # have stalled requests for >5 min and pinned every uvicorn threadpool
        # worker. The SDK also retries failed requests up to 2 times by default,
        # which silently triples the wall-clock budget — disable retries so the
        # explore service's deterministic fallback kicks in promptly on stalls.
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
        )
        self._model = model
        self.name = name
        self._json_mode = json_mode

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> JSONResponse:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if self._json_mode:
            request["response_format"] = {"type": "json_object"}
        completion = self._client.chat.completions.create(**request)

        choice = completion.choices[0]
        text = choice.message.content or ""
        usage = getattr(completion, "usage", None)
        return JSONResponse(
            text=text,
            model=getattr(completion, "model", self._model),
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        )
