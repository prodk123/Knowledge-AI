"""Agent Pydantic schemas for structured LLM parsing."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    ABSTAINED = "ABSTAINED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class ActionType(str, Enum):
    TOOL_CALL = "TOOL_CALL"
    SYNTHESIZE = "SYNTHESIZE"
    FINALIZE = "FINALIZE"
    NO_OP = "NO_OP"


class AgentPlanStepSchema(BaseModel):
    step_id: str = Field(..., description="A unique identifier for this step, e.g., 'step_1'.")
    action_type: ActionType = Field(..., description="The type of action to perform.")
    tool_name: str | None = Field(default=None, description="The name of the tool, if action_type is TOOL_CALL.")
    purpose: str = Field(..., description="Why this step is necessary.")
    dependencies: list[str] = Field(default_factory=list, description="List of step_ids that must complete before this step.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool. Can reference previous step outputs using $step_id syntax.")

class AgentPlan(BaseModel):
    goal: str = Field(..., description="The overall goal to achieve.")
    steps: list[AgentPlanStepSchema] = Field(..., description="List of structured steps forming a valid Directed Acyclic Graph (DAG).")
    reasoning_summary: str = Field(..., description="Brief summary of the reasoning for this plan.")
    completion_condition: str = Field(..., description="What constitutes completion of this plan.")

class AgentSynthesizeOutput(BaseModel):
    final_answer: str | None = Field(default=None, description="The synthesized response based on context.")
    is_complete: bool = Field(..., description="True if the entire task is now complete.")
    
class RAGSearchArguments(BaseModel):
    query: str = Field(..., description="The search query.")

