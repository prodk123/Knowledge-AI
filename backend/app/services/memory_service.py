"""Service for managing persistent memory."""

import logging
import uuid
from datetime import datetime
from typing import Any
import hashlib

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams, Filter, FieldCondition, MatchValue
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.models.memory import Memory
from app.agent.memory.policy import MemoryProposal, MemoryPolicyEngine
from app.rag.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)


class MemoryService:
    """Handles CRUD and vector indexing for memories."""

    def __init__(self, session: AsyncSession, embedding_provider: EmbeddingProvider):
        self.session = session
        self.embedding_provider = embedding_provider
        self.qdrant = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        self.collection_name = "memories" # Default memory collection
        self.dimension = settings.embedding_dimension
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        try:
            if not self.qdrant.collection_exists(self.collection_name):
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
                )
        except Exception as e:
            logger.error("Failed to ensure memory collection: %s", e)

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def propose_memory(self, proposal: MemoryProposal, user_id: str, tenant_id: str | None = None) -> Memory | None:
        """Evaluate a proposal and persist if valid."""
        
        # 1. Evaluate Policy
        if not MemoryPolicyEngine.validate_proposal(proposal):
            logger.info("Memory proposal rejected by policy.")
            return None

        # 2. Check deduplication
        content_hash = self._hash_content(proposal.content)
        stmt = select(Memory).where(
            Memory.user_id == user_id, 
            Memory.content_hash == content_hash,
            Memory.status == "ACTIVE"
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            logger.debug("Memory already exists for user.")
            return existing

        # 3. Create DB Record
        memory = Memory(
            id=uuid.uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            memory_type=proposal.memory_type,
            content=proposal.content,
            structured_value=proposal.structured_value,
            source_type=proposal.source_type,
            source_reference=proposal.source_reference,
            trust_level=proposal.trust_level,
            confidence=proposal.confidence,
            importance=proposal.importance,
            status="ACTIVE",
            content_hash=content_hash,
            metadata_={}
        )
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)

        # 4. Index in Qdrant (Semantic search is only really useful for SEMANTIC and EPISODIC, but we'll index ACTIVE)
        if proposal.memory_type in ["SEMANTIC", "EPISODIC"]:
            try:
                embedding = self.embedding_provider.embed_query(proposal.content)
                payload = {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "memory_type": proposal.memory_type,
                    "status": "ACTIVE",
                    "importance": proposal.importance,
                    "trust_level": proposal.trust_level,
                    "content": proposal.content
                }
                self.qdrant.upsert(
                    collection_name=self.collection_name,
                    points=[PointStruct(id=str(memory.id), vector=embedding, payload=payload)]
                )
            except Exception as e:
                logger.error("Failed to index memory in Qdrant: %s", e)
                # Fail open for vector, DB is authoritative. (Could implement reindex mechanism)

        return memory

    async def get_memories(self, user_id: str, memory_type: str | None = None) -> list[Memory]:
        """Fetch memories for a user."""
        stmt = select(Memory).where(Memory.user_id == user_id, Memory.status == "ACTIVE")
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete_memory(self, memory_id: uuid.UUID, user_id: str) -> bool:
        """Mark memory as DELETED and remove from Qdrant."""
        stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        memory = (await self.session.execute(stmt)).scalars().first()
        
        if not memory:
            return False
            
        memory.status = "DELETED"
        await self.session.commit()
        
        try:
            self.qdrant.delete(
                collection_name=self.collection_name,
                points_selector=[str(memory_id)]
            )
        except Exception:
            pass # Soft failure, it will just not be retrieved if status is checked
            
        return True
