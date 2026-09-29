"""Schemas for Swarm Orchestration."""

from typing import Any
from pydantic import BaseModel, Field

class AgentDelegationRequest(BaseModel):
    """Schema for a request from a supervisor to a specialized agent."""
    agent_id: str = Field(description="The ID of the agent to delegate to (e.g., 'research_agent', 'rag_agent').")
    task: str = Field(description="The specific task or instruction for the specialized agent.")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional structured context (e.g., tool outputs or memory facts).")

class AgentObservation(BaseModel):
    """Schema for the result returned by a specialized agent."""
    agent_id: str = Field(description="The ID of the agent that performed the work.")
    status: str = Field(description="COMPLETED or FAILED.")
    output: Any = Field(description="The final output from the agent.")
    error: str | None = Field(default=None, description="Error message, if any.")
    latency_ms: float = Field(default=0.0)

class AgentMessage(BaseModel):
    """Schema for inter-agent messages."""
    sender_id: str
    receiver_id: str
    content: str
    message_type: str = Field(default="TASK", description="TASK, OBSERVATION, or ERROR")
