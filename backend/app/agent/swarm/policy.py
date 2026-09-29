"""Policy Engine and Authorization for Swarm Orchestration."""

import logging
from typing import Any

from app.agent.tools.base import RequestContext
from app.agent.swarm.schemas import AgentDelegationRequest

logger = logging.getLogger(__name__)

class AgentAuthorizationService:
    """Validates user and tenant RBAC for agent invocation."""
    
    def __init__(self, tenant_id: str | None = None):
        self.tenant_id = tenant_id

    def authorize(self, agent_id: str, context: RequestContext) -> bool:
        """
        Determine if the context (user/role) has permission to invoke the agent.
        For example, 'finance_agent' might require 'role:finance'.
        For now, all base specialized agents are allowed for any authorized user,
        but we can extend this to check specific capabilities.
        """
        # In a real enterprise system, we would query the DB for agent-specific role mappings.
        # Here we just ensure the user is authenticated (which RequestContext implies).
        if not context.user_id:
            logger.warning("Agent %s invocation denied: No user_id in context.", agent_id)
            return False
        return True


class AgentPolicyEngine:
    """Enforces boundaries and delegation graphs within the swarm."""
    
    # Define allowed delegation edges: source_agent -> list of allowed target agents
    ALLOWED_DELEGATIONS = {
        "supervisor": ["research_agent", "rag_agent", "analysis_agent", "synthesis_agent"],
        "research_agent": [],    # Leaf agent, cannot delegate
        "rag_agent": [],         # Leaf agent
        "analysis_agent": [],    # Leaf agent
        "synthesis_agent": [],   # Leaf agent
        "base_agent": []
    }
    
    def validate_delegation(self, source_agent_id: str, target_agent_id: str) -> bool:
        """Check if source agent is allowed to delegate to target agent."""
        allowed_targets = self.ALLOWED_DELEGATIONS.get(source_agent_id, [])
        if target_agent_id not in allowed_targets:
            logger.error(
                "Policy violation: Delegation from %s to %s is blocked.",
                source_agent_id, target_agent_id
            )
            return False
        return True
    
    def sanitize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize context passed to a child agent.
        Child agents receive minimal context (no system prompts, no arbitrary commands).
        """
        # Create a clean copy, dropping any keys that might override behavior
        clean_context = {}
        for k, v in context.items():
            if k not in ["system_prompt", "override_policies", "secrets"]:
                clean_context[k] = v
        return clean_context
