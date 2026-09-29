"""Memory API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.db.database import async_session_factory
from app.models.auth import User
from app.models.memory import Memory
from app.services.memory_service import MemoryService
from app.rag.embeddings import get_embedding_provider
from app.core.config import settings

router = APIRouter()

# Schema for responses
class MemoryResponse(BaseModel):
    id: uuid.UUID
    memory_type: str
    content: str
    source_type: str
    trust_level: str
    importance: int
    status: str
    
    class Config:
        orm_mode = True
        from_attributes = True


async def get_memory_service() -> MemoryService:
    from app.services.memory_service import MemoryService
    # Note: Embedding service shouldn't be fully instantiated inside deps repeatedly in prod,
    # but for this stage we'll create it here.
    async with async_session_factory() as session:
        emb = get_embedding_provider(settings)
        yield MemoryService(session, emb)


@router.get("/", response_model=list[MemoryResponse])
async def list_memories(
    memory_type: str | None = Query(None, description="Filter by WORKING, EPISODIC, or SEMANTIC"),
    current_user: User = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service)
):
    """List active memories for the current user."""
    memories = await memory_service.get_memories(str(current_user.id), memory_type)
    return memories

@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service)
):
    """Delete a memory (sets status to DELETED and removes from vector store)."""
    success = await memory_service.delete_memory(memory_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or unauthorized")
    return None
