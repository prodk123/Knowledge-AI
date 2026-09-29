"""Base interface for Specialized Agents in the Swarm."""

import abc
from typing import Any

from app.agent.tools.base import RequestContext
from app.agent.swarm.schemas import AgentDelegationRequest, AgentObservation


class BaseSpecializedAgent(abc.ABC):
    """Abstract base class for all specialized agents in the Swarm."""
    
    agent_id: str = "base_agent"
    description: str = "A generic specialized agent."
    capabilities: list[str] = []
    
    @abc.abstractmethod
    async def execute(self, request: AgentDelegationRequest, context: RequestContext) -> AgentObservation:
        """
        Execute the delegated task.
        
        Args:
            request: The task instruction and context.
            context: The execution context (user_id, roles, conversation_id, etc.).
            
        Returns:
            An AgentObservation containing the result or error.
        """
        pass
