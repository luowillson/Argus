"""LLMProvider — minimal contract so we can swap Z.AI / Gemini / OpenAI / Anthropic.

The MVP only needs one shape: a JSON-mode chat completion. If a provider can't do
strict JSON output, the caller is responsible for the retry-and-parse loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class JSONResponse:
    text: str  # raw JSON string from the model
    model: str  # which model actually answered
    input_tokens: int | None
    output_tokens: int | None


class LLMProvider(ABC):
    name: str  # short identifier used in logs and stored on ai_insights.model

    @abstractmethod
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_output_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> JSONResponse:
        """Return a JSON object as a raw string. Implementations should set the
        provider's JSON-mode flag if available."""
