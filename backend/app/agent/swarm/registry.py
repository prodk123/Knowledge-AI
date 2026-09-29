"""Agent Registry for Swarm Orchestration."""

import logging
from typing import Type

from app.agent.swarm.agents.base import BaseSpecializedAgent

logger = logging.getLogger(__name__)

class AgentRegistry:
    """Central registry for available specialized agents in the Swarm."""
    
    def __init__(self):
        self._agents: dict[str, BaseSpecializedAgent] = {}
        
    def register(self, agent: BaseSpecializedAgent) -> None:
        """Register a new specialized agent."""
        if agent.agent_id in self._agents:
            logger.warning("Overwriting existing agent with ID: %s", agent.agent_id)
        self._agents[agent.agent_id] = agent
        logger.info("Registered specialized agent: %s", agent.agent_id)
        
    def get_agent(self, agent_id: str) -> BaseSpecializedAgent:
        """Retrieve an agent by ID."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent '{agent_id}' not found in registry.")
        return self._agents[agent_id]
        
    def get_all_agents(self) -> list[BaseSpecializedAgent]:
        """List all registered agents."""
        return list(self._agents.values())
        
    def get_agent_descriptions(self) -> list[dict[str, str]]:
        """Return a summary of available agents for planning."""
        return [
            {
                "agent_id": agent.agent_id,
                "description": agent.description,
                "capabilities": ", ".join(agent.capabilities)
            }
            for agent in self._agents.values()
        ]
