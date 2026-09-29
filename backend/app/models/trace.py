from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

class Trace(Base):
    """A complete RAG pipeline trace."""
    __tablename__ = "traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String, index=True, nullable=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    route = Column(String, nullable=True) # e.g., "RAG", "DIRECT"
    status = Column(String, default="ok") # "ok", "error"
    
    total_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    spans = relationship("Span", back_populates="trace", cascade="all, delete-orphan")

class Span(Base):
    """An individual operation within a trace (e.g., dense_retrieval, llm_generation)."""
    __tablename__ = "spans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(UUID(as_uuid=True), ForeignKey("traces.id"), nullable=False)
    
    name = Column(String, nullable=False) # e.g., "query_router", "dense_retrieval", "generation"
    status = Column(String, default="ok")
    
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    latency_ms = Column(Float, nullable=True)
    
    metadata_json = Column(JSON, nullable=True) # Store model names, retrieved chunk count, etc.
    
    trace = relationship("Trace", back_populates="spans")
