"""Ephemeral Agent State."""

import time
import uuid
from typing import Any
from dataclasses import dataclass, field

from app.agent.schemas import AgentPlan, AgentStatus


@dataclass
class AgentObservation:
    step_id: str
    action_type: str
    tool_name: str | None
    status: str
    result_summary: str
    latency_ms: float
    evidence_references: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class AgentState:
    """In-memory representation of an ongoing agent run."""
    run_id: uuid.UUID
    request_id: str
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    
    task: str
    plan: AgentPlan | None = None
    
    status: AgentStatus = AgentStatus.PENDING
    
    current_step: int = 0
    observations: list[AgentObservation] = field(default_factory=list)
    
    final_answer: str | None = None
    error: str | None = None
    
    iteration_count: int = 0
    token_usage: int = 0
    tool_call_count: int = 0
    estimated_cost: float = 0.0
    
    started_at: float = field(default_factory=time.time)
    
    # Limits
    max_iterations: int = 10
    max_steps: int = 15
    max_tokens: int = 20000
    max_tool_calls: int = 10
    max_time_seconds: int = 60
    
    def check_limits(self) -> None:
        """Evaluate if any limits are exceeded. Raises TimeoutError or ValueError."""
        if self.iteration_count >= self.max_iterations:
            self.status = AgentStatus.FAILED
            self.error = "Max iterations exceeded."
            raise ValueError(self.error)
            
        if self.current_step >= self.max_steps:
            self.status = AgentStatus.FAILED
            self.error = "Max steps exceeded."
            raise ValueError(self.error)
            
        if self.tool_call_count >= self.max_tool_calls:
            self.status = AgentStatus.FAILED
            self.error = "Max tool calls exceeded."
            raise ValueError(self.error)
            
        if self.token_usage >= self.max_tokens:
            self.status = AgentStatus.FAILED
            self.error = "Max tokens exceeded."
            raise ValueError(self.error)
            
        if time.time() - self.started_at > self.max_time_seconds:
            self.status = AgentStatus.TIMEOUT
            self.error = "Agent execution timed out."
            raise TimeoutError(self.error)
            
    def format_history(self) -> str:
        """Format the execution history into a string for the LLM."""
        if not self.observations:
            return "No actions taken yet."
            
        history = ""
        for obs in self.observations:
            history += f"\n--- Step {obs.step_id} ---\n"
            if obs.action_type == "TOOL_CALL":
                history += f"Action: {obs.action_type} (Tool: {obs.tool_name})\n"
            else:
                history += f"Action: {obs.action_type}\n"
            history += f"Status: {obs.status}\n"
            if obs.error:
                history += f"Error: {obs.error}\n"
            else:
                history += f"Result: {obs.result_summary}\n"
                if obs.evidence_references:
                    history += f"Evidence: {len(obs.evidence_references)} items retrieved.\n"
        return history
