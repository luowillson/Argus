from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def encode(self, texts: list[str]) -> list[list[float]]: ...
