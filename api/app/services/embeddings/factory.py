from __future__ import annotations

from app.services.embeddings.provider import EmbeddingProvider

_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Return a module-level singleton SBERT provider (model loaded on first call)."""
    global _provider
    if _provider is None:
        from app.config import get_settings
        from app.services.embeddings.sbert import SBERTProvider

        _provider = SBERTProvider(get_settings().embedding_model)
    return _provider
