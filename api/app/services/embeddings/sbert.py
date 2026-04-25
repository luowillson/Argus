from __future__ import annotations

from app.services.embeddings.provider import EmbeddingProvider


class SBERTProvider(EmbeddingProvider):
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy; loaded lazily

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()  # type: ignore[return-value]
