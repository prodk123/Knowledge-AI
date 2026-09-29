"""Embedding provider — abstraction over embedding model implementations.

Supports:
- openrouter (API-based, via OpenAI-compatible client, default)
- A placeholder for future local providers

The rest of the application should not know which provider is being used.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    This interface allows swapping between local and API-based embedding
    models without changing any downstream code.
    """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of document texts."""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Generate an embedding for a single query string."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        ...


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using any OpenAI-compatible API (OpenRouter, OpenAI, etc).

    Uses the openai Python client pointed at the configured base_url.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        dimension: int = 768,
    ):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model_name = model_name
        self._dim = dimension
        logger.info("OpenAI-compatible embedding provider initialized: %s (dim=%d)", model_name, dimension)

    def _create_kwargs(self, input_data, input_type: str = "passage") -> dict:
        """Build kwargs for the embeddings.create() call."""
        kwargs = {"model": self._model_name, "input": input_data}
        # For NVIDIA NIM asymmetric models
        if "nvidia/" in self._model_name:
            kwargs["extra_body"] = {"input_type": input_type}
        return kwargs

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Process in batches to avoid API limits
        batch_size = 20
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self._client.embeddings.create(
                    **self._create_kwargs(batch, input_type="passage")
                )
                all_embeddings.extend([item.embedding for item in response.data])
            except Exception as e:
                logger.warning(f"Embedding API failed for document batch ({e}). Returning dummy vectors.")
                all_embeddings.extend([[1e-5] * self._dim for _ in batch])

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        try:
            response = self._client.embeddings.create(
                **self._create_kwargs(query, input_type="query")
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embedding API failed ({e}). Gracefully degrading to BM25 lexical search.")
            # Return a tiny non-zero vector to avoid division by zero in cosine similarity
            return [1e-5] * self._dim

    @property
    def dimension(self) -> int:
        return self._dim


def get_embedding_provider(settings) -> EmbeddingProvider:
    """Factory function to create the appropriate embedding provider.

    Reads EMBEDDING_PROVIDER from settings and returns the corresponding
    implementation.
    """
    provider = settings.embedding_provider.lower()

    if provider in ("openrouter", "openai"):
        return OpenAICompatibleEmbeddingProvider(
            model_name=settings.embedding_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            dimension=settings.embedding_dimension,
        )
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider}. "
            f"Supported: openrouter, openai"
        )
