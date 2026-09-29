"""Memory models — SQLAlchemy ORM."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, DateTime, Integer, Float, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Memory(Base):
    """PostgreSQL table for persistent agent memory."""
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False) # WORKING, EPISODIC, SEMANTIC
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    
    source_type: Mapped[str] = mapped_column(String(50), nullable=False) # USER_EXPLICIT, CONVERSATION, AGENT_INFERENCE, WORKFLOW, TOOL_RESULT, ADMIN_DEFINED
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True) # e.g. run_id, conversation_id
    
    trust_level: Mapped[str] = mapped_column(String(50), nullable=False, default="inferred") # explicit, inferred, untrusted
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE") # ACTIVE, ARCHIVED, DELETED, EXPIRED, QUARANTINED
    
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
