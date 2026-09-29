"""Dense Retriever — retrieves chunks using vector similarity."""

import logging

from app.models.chat import RetrievalResult
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


class DenseRetriever:
    """Retrieves document chunks using semantic vector search."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int, allowed_roles: list[str] | None = None) -> list[RetrievalResult]:
        """Perform dense retrieval and populate dense ranking fields."""
        logger.info("Executing dense retrieval for top %d", top_k)
        
        query_embedding = self.embedding_provider.embed_query(query)
        results = self.vector_store.search(
            query_embedding=query_embedding, 
            top_k=top_k, 
            allowed_roles=allowed_roles
        )

        # Populate dense tracking fields
        for rank, result in enumerate(results, start=1):
            result.retriever = "dense"
            result.dense_rank = rank
            result.dense_score = result.score

        logger.info("Dense retrieval completed with %d results", len(results))
        return results
