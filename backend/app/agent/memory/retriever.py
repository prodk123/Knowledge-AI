"""Retrieves relevant memory for the agent context."""

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.core.config import settings
from app.rag.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

class MemoryResult:
    def __init__(self, id: str, content: str, memory_type: str, importance: int, score: float, trust_level: str):
        self.id = id
        self.content = content
        self.memory_type = memory_type
        self.importance = importance
        self.score = score
        self.trust_level = trust_level

class MemoryRetriever:
    """Retrieves relevant memory safely."""
    
    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedding_provider = embedding_provider
        self.qdrant = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        self.collection_name = "memories"
        
    async def retrieve_relevant_memory(self, query: str, user_id: str, tenant_id: str | None = None, top_k: int = 5) -> list[MemoryResult]:
        """
        Retrieves top memories via semantic search, strictly isolated by user_id.
        """
        try:
            # Check if collection exists first to avoid errors on fresh installs
            if not self.qdrant.collection_exists(self.collection_name):
                return []
                
            embedding = self.embedding_provider.embed_query(query)
            
            # STRICT ISOLATION BY USER_ID
            must_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                FieldCondition(key="status", match=MatchValue(value="ACTIVE"))
            ]
            
            if tenant_id:
                must_conditions.append(FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)))
                
            query_filter = Filter(must=must_conditions)
            
            search_result = self.qdrant.query_points(
                collection_name=self.collection_name,
                query=embedding,
                limit=top_k,
                query_filter=query_filter
            )
            
            results = []
            for point in search_result.points:
                payload = point.payload or {}
                # Filter by similarity threshold (e.g. 0.75) if desired, skipping for now
                # Or use importance score to boost
                results.append(
                    MemoryResult(
                        id=str(point.id),
                        content=payload.get("content", ""), # Oh wait! The text content isn't in payload! 
                        # I must modify memory_service.py to include content in payload. Let me fix that.
                        memory_type=payload.get("memory_type", "SEMANTIC"),
                        importance=payload.get("importance", 3),
                        score=point.score,
                        trust_level=payload.get("trust_level", "inferred")
                    )
                )
                
            return results
        except Exception as e:
            logger.error("Failed to retrieve memory: %s", e)
            return []
