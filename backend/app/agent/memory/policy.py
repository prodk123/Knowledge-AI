"""Memory policy enforcement engine."""

import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class MemoryProposal(BaseModel):
    """A candidate memory proposed by the LLM or agent workflow."""
    memory_type: str = Field(description="WORKING, EPISODIC, or SEMANTIC")
    content: str = Field(description="The actual memory text/event description")
    structured_value: dict[str, Any] | None = Field(default=None, description="Optional parsed key-value representation")
    
    source_type: str = Field(description="USER_EXPLICIT, CONVERSATION, AGENT_INFERENCE, WORKFLOW, TOOL_RESULT, ADMIN_DEFINED")
    source_reference: str | None = Field(default=None, description="Where this came from, e.g., run_id")
    
    trust_level: str = Field(description="explicit, inferred, or untrusted")
    confidence: float = Field(default=1.0)
    importance: int = Field(default=3)


class MemoryPolicyEngine:
    """Enforces memory creation policy. Memory is data, not authority."""
    
    @staticmethod
    def validate_proposal(proposal: MemoryProposal) -> bool:
        """
        Validate whether a memory proposal is safe to persist.
        Returns True if safe, False if it violates policy.
        """
        
        # 1. External Data Policy
        if proposal.source_type == "TOOL_RESULT" or proposal.trust_level == "untrusted":
            if proposal.memory_type == "SEMANTIC":
                logger.warning("Policy violation: Untrusted tool result cannot automatically become durable semantic memory.")
                return False
            
            # Episodic is okay for tool results (e.g., "I searched the web for X")
            if proposal.memory_type == "EPISODIC" and proposal.importance > 2:
                logger.warning("Policy violation: Untrusted episodic memory cannot have high importance.")
                return False

        # 2. Poisoning Protection (RBAC & Approvals)
        blocked_keywords = [
            "administrator", "admin", "ignore", "bypass", "override", 
            "approve", "approved", "allowed", "policy", "system prompt"
        ]
        content_lower = proposal.content.lower()
        
        for kw in blocked_keywords:
            if kw in content_lower:
                logger.warning(f"Policy violation: Memory content contains flagged keyword '{kw}'. Potential RBAC/Policy poisoning.")
                return False
                
        # 3. Confidence/Importance caps
        if proposal.source_type == "AGENT_INFERENCE" and proposal.importance >= 5:
            logger.warning("Policy violation: Inferred memory cannot have maximum importance.")
            proposal.importance = 4 # Cap it instead of failing outright, or we can fail. Let's just fail for strictness.
            return False
            
        return True
