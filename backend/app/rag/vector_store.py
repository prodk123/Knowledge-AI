"""Vector store — abstraction over Qdrant operations."""

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import Settings
from app.models.chat import RetrievalResult
from app.rag.chunker import DocumentChunk

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Manages Qdrant collections and vector operations."""

    def __init__(self, settings: Settings):
        self.client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        self.collection_name = settings.qdrant_collection
        self.dimension = settings.embedding_dimension
        logger.info(
            "Qdrant client initialized (url=%s, collection=%s, dim=%d)",
            settings.qdrant_url,
            self.collection_name,
            self.dimension,
        )

    def ensure_collection(self) -> None:
        """Create the collection if it doesn't exist. Idempotent."""
        try:
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension, distance=Distance.COSINE
                    ),
                )
                logger.info("Created Qdrant collection: %s", self.collection_name)
            else:
                logger.debug("Qdrant collection %s already exists", self.collection_name)
        except Exception as e:
            logger.error("Failed to ensure Qdrant collection: %s", e)
            raise

    def store_chunks(
        self, chunks: list[DocumentChunk], embeddings: list[list[float]]
    ) -> None:
        """Upsert document chunks and their embeddings into Qdrant."""
        if not chunks or not embeddings:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(chunks)} chunks, {len(embeddings)} embeddings"
            )

        points = []
        for chunk, embedding in zip(chunks, embeddings):
            # Include the text in the payload so we can retrieve it later
            payload: dict[str, Any] = {
                "text": chunk.text,
                **chunk.metadata,
            }
            points.append(
                PointStruct(
                    id=chunk.chunk_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        # Upsert in batches (Qdrant client handles the actual HTTP batching)
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("Upserted %d points to Qdrant", len(points))

    def search(
        self, query_embedding: list[float], top_k: int = 5, allowed_roles: list[str] | None = None
    ) -> list[RetrievalResult]:
        """Search for the most similar chunks to the query embedding."""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchAny
            
            query_filter = None
            if allowed_roles is not None:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="allowed_roles",
                            match=MatchAny(any=allowed_roles)
                        )
                    ]
                )

            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=top_k,
                query_filter=query_filter,
            )

            results = []
            for point in search_result.points:
                payload = point.payload or {}
                results.append(
                    RetrievalResult(
                        chunk_id=str(point.id),
                        document_id=payload.get("document_id", ""),
                        text=payload.get("text", ""),
                        score=point.score,
                        metadata=payload,
                    )
                )
            return results
        except Exception as e:
            logger.error("Qdrant search failed: %s", e)
            raise
