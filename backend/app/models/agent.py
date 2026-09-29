"""Agent models — SQLAlchemy ORM."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, DateTime, ForeignKey, Integer, Float, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.conversation import Conversation


class AgentRun(Base):
    """PostgreSQL table for tracking bounded agent execution runs."""
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_id: Mapped[str] = mapped_column(String(255), nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation")
    steps: Mapped[list["AgentStep"]] = relationship(
        "AgentStep", back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.created_at"
    )


class AgentStep(Base):
    """PostgreSQL table for individual steps executed during an AgentRun."""
    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    step_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "PLAN", "TOOL_CALL", "FINALIZE"
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True) # The tool invoked, if any
    status: Mapped[str] = mapped_column(String(50), nullable=False)    # e.g. "COMPLETED", "FAILED"
    
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="steps")


class AgentPlan(Base):
    """PostgreSQL table for bounded multi-step agent plans."""
    __tablename__ = "agent_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    
    # Swarm fields
    max_agents: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_delegations: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=100000)
    
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    run: Mapped["AgentRun"] = relationship("AgentRun")
    plan_steps: Mapped[list["AgentPlanStep"]] = relationship(
        "AgentPlanStep", back_populates="plan", cascade="all, delete-orphan", order_by="AgentPlanStep.sequence"
    )


class AgentPlanStep(Base):
    """PostgreSQL table for individual planned workflow steps in a DAG."""
    __tablename__ = "agent_plan_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    step_id: Mapped[str] = mapped_column(String(100), nullable=False) # The LLM-generated string ID, e.g., "step_1"
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Swarm fields
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True) # If this is a delegation to an agent
    parent_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    
    dependencies: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    arguments: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True) # Static or referenced inputs
    
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Integer, nullable=False, default=0) # using Integer as bool mapping in some DBs, or bool if strict
    
    retries_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    plan: Mapped["AgentPlan"] = relationship("AgentPlan", back_populates="plan_steps")

